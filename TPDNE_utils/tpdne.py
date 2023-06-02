import os
import numpy as np
from time import time, sleep
from pathlib import Path
from functools import wraps
from PIL import Image

from beartype import beartype
from beartype.typing import Callable

@beartype
def sample_image_and_save_repeatedly(
    fn: Callable[..., np.ndarray],         # function that returns a ndarray of shape (3, <width>, <height>)
    output_path: str = './out/random',     # path to the output image, without extension (will be saved as webp)
    *,
    call_every_ms: int = 250,              # how often to sample
    tmp_dir: str = '/tmp',                 # to store temporary images, before symbolically linking to the output path
    num_rotated_tmp_images: int = 10,
    image_format: str = 'webp',
    verbose: bool = True,
    quality = 99,
    generate_favicon: bool = True,
    favicon_size: int = 32
):
    assert 0 < quality <= 100
    assert favicon_size in {16, 32}
    assert image_format in {'webp', 'png', 'jpeg'}

    tmp_dir = Path(tmp_dir)
    output_path = Path(output_path)
    assert output_path.suffix == '', 'output path suffix will be automatically determined by `image_format` keyword arg'

    output_path = output_path.with_suffix(f'.{image_format}')

    call_every_seconds = call_every_ms / 1000

    assert tmp_dir.is_dir()
    output_path.parents[0].mkdir(parents = True, exist_ok = True)

    tmp_image_index = 0

    while True:
        start = time()
        image_tensor = fn()

        tmp_image_index = (tmp_image_index + 1) % num_rotated_tmp_images
        tmp_path = str(tmp_dir / f'{tmp_image_index}.{image_format}')

        pil_image = Image.fromarray(image_tensor, 'RGB')
        pil_image.save(tmp_path, format = image_format, quality = quality)
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

        if elapsed >= call_every_seconds:
            continue

        sleep(call_every_seconds - elapsed)
