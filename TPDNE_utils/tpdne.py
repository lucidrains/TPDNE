import os
import sys
import numpy as np
from time import time, sleep
from pathlib import Path
from functools import wraps
from PIL import Image

from beartype import beartype
from beartype.typing import Callable, Optional

from einops import rearrange, repeat

# templating

from jinja2 import Environment, FileSystemLoader

script_path = Path(__file__)
current_dir = script_path.parents[0]
environment = Environment(loader = FileSystemLoader(str(current_dir)))

nginx_template = environment.get_template('nginx.conf.tmpl')
systemd_service_template = environment.get_template('tpdne.service.tmpl')

# helper functions

def exists(val):
    return val is not None

# handle everything that was confusing to me when first encountering image tensors

def auto_handle_image_tensor(t):
    if t.ndim == 4:
        # assume batch is first dimension and take first sample
        t = t[0]

    if t.ndim == 2:
        # very rare case, but assume greyscale
        t = rearrange(t, 'h w -> h w 1')

    if t.shape[0] <= 3:
        # channel first
        t = rearrange(t, 'c h w -> h w c')

    assert t.shape[-1] <= 3, 'image tensor must be returned in the shape (height, width, channels), where channels is either 3 or 1'

    if t.shape[-1] == 1:
        t = repeat(t, 'h w 1 -> h w c', c = 3)

    # handle scale

    if t.dtype == np.float:
        has_negatives = np.any(t < 0)

        if has_negatives:
            t = t * 127.5 + 128
        else:
            t = t * 255

        t = t.astype(np.uint8)

    return t.clip(0, 255)

# main function

@beartype
def sample_image_and_save_repeatedly(
    fn: Callable[..., np.ndarray],         # function that returns a ndarray of shape (3, <width>, <height>)
    output_path: str = './out/random',     # path to the output image, without extension (will be saved as webp)
    *,
    call_every_ms: int = 250,              # how often to sample
    tmp_dir: str = '/tmp',                 # to store temporary images, before symbolically linking to the output path
    num_rotated_tmp_images: int = 10,
    image_format: str = 'jpeg',
    verbose: bool = True,
    quality = 99,
    resize_image_to: Optional[int] = None,
    generate_favicon: bool = True,
    favicon_size: int = 32,
    generate_nginx_conf: bool = True,
    symbolic_link_nginx_conf: bool = True,
    nginx_sites_available_path: str = '/etc/nginx/sites-available',
    nginx_conf_filename = 'default',
    generate_systemd_service_conf: bool = False,
    systemd_service_path: str = '/etc/systemd/system',
    systemd_service_name = 'tpdne',
    domain_name = '_'
):
    assert 0 < quality <= 100
    assert favicon_size in {16, 32}
    assert image_format in {'jpeg', 'png', 'webp'}

    tmp_dir = Path(tmp_dir)
    output_path = Path(output_path)

    assert output_path.suffix == '', 'output path suffix will be automatically determined by `image_format` keyword arg'

    output_path = output_path.with_suffix(f'.{image_format}')

    call_every_seconds = call_every_ms / 1000

    assert tmp_dir.is_dir()
    root = output_path.parents[0]
    root.mkdir(parents = True, exist_ok = True)

    tmp_image_index = 0

    # linking nginx

    if generate_nginx_conf:
        nginx_sites_path = Path(nginx_sites_available_path)
        nginx_sites_conf_path = nginx_sites_path / nginx_conf_filename

        assert nginx_sites_path.is_dir()

        nginx_conf_text = nginx_template.render(
            root = str(root.resolve()),
            index = output_path.name,
            server_name = domain_name
        )

        tmp_conf_path = Path(tmp_dir / 'nginx.server.conf')
        tmp_conf_path.write_text(nginx_conf_text)

        print(f'nginx server conf generated at {str(tmp_conf_path)}')

        if symbolic_link_nginx_conf:
            os.system(f'ln -nfs {str(tmp_conf_path)} {nginx_sites_conf_path}')

            print(f'nginx conf linked to {nginx_sites_conf_path}\nrun `systemctl reload nginx` for it to be in effect')

    if generate_systemd_service_conf and not exists(os.getenv('LAUNCHED_FROM_SYSTEMD', None)):

        systemd_service_path = Path(systemd_service_path)
        systemd_service_conf_path = systemd_service_path / f'{systemd_service_name}.service'

        assert systemd_service_path.is_dir()

        systemd_conf_text = systemd_service_template.render(
            working_directory = str(current_dir.resolve()),
            python_executable = sys.executable,
            script_path = str(script_path.resolve())
        )

        tmp_service_path = Path(tmp_dir / 'tpdne.services')
        tmp_service_path.write_text(systemd_conf_text)

        os.system(f'ln -nfs {str(tmp_service_path)} {str(systemd_service_conf_path)}')

        print(f'service {systemd_service_name}.service created at {str(systemd_service_conf_path)}')
        print(f'run `systemctl enable {systemd_service_name}.service` to start this script')
        print(f'then run `systemctl status {systemd_service_name}.service` to see the status')
        exit()

    # invoke `fn` in a while loop

    while True:
        start = time()
        image_tensor = fn()

        image_tensor = auto_handle_image_tensor(image_tensor)

        tmp_image_index = (tmp_image_index + 1) % num_rotated_tmp_images
        tmp_path = str(tmp_dir / f'{tmp_image_index}.{image_format}')

        pil_image = Image.fromarray(image_tensor, 'RGB')

        if exists(resize_image_to):
            pil_image = pil_image.resize((resize_image_to, resize_image_to))

        # depending on image format, pass in different kwargs on pillow image save

        image_save_kwargs = dict()

        if image_format == 'jpeg':
            image_save_kwargs = dict(optimize = True, progressive = True)
        elif image_format == 'webp':
            image_save_kwargs = dict(format = 'webp')

        # save image to tmp path

        pil_image.save(tmp_path, quality = quality, **image_save_kwargs)

        # symbolically link to the live output path
        # if one tries to serve directly from the tmp path, client can receive incomplete images

        os.system(f'ln -nfs {tmp_path} {output_path}')

        if generate_favicon:
            tmp_favicon_path = str(tmp_dir / f'favicon_{tmp_image_index}.png')
            output_favicon_path = output_path.parents[0] / 'favicon.png'

            small_pil_image = pil_image.resize((favicon_size, favicon_size))
            small_pil_image.save(tmp_favicon_path)
            os.system(f'ln -nfs {tmp_favicon_path} {output_favicon_path}')

        elapsed = time() - start

        if verbose:
            print(f'{elapsed:.3f}s - tmp image at {tmp_path}, output image at {output_path}')

        # make sure images are generated at least after `call_every_ms` milliseconds

        if elapsed >= call_every_seconds:
            continue

        sleep(call_every_seconds - elapsed)
