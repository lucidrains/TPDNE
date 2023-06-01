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
    tmp_dir = '/tmp',                      # to store temporary images, before symbolically linking to the output path
    num_rotated_tmp_images = 10,
    verbose: bool = True
):
    tmp_dir = Path(tmp_dir)
    output_path = Path(output_path).with_suffix('.webp')
    call_every_seconds = call_every_ms / 1000

    assert tmp_dir.is_dir()
    output_path.parents[0].mkdir(parents = True, exist_ok = True)

    tmp_image_index = 0

    while True:
        start = time()
        image_tensor = fn()

        tmp_image_index = (tmp_image_index + 1) % num_rotated_tmp_images
        tmp_path = str(tmp_dir / f'{tmp_image_index}.webp')

        Image.fromarray(image_tensor, 'RGB').save(tmp_path, format = 'webp')
        os.system(f'ln -nfs {tmp_path} {output_path}')

        elapsed = time() - start

        if verbose:
            print(f'{elapsed:.3f}s - tmp image at {tmp_path}, output image at {output_path}')

        if elapsed >= call_every_seconds:
            continue

        sleep(call_every_seconds - elapsed)
