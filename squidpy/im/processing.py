"""Functions exposed: process_img()."""

from types import MappingProxyType
from typing import Any, Union, Mapping, Optional

import skimage
import skimage.filters

from squidpy._docs import d, inject_docs
from squidpy.constants._constants import Processing
from .object import ImageContainer


@d.dedent
@inject_docs(p=Processing)
def process_img(
    img: ImageContainer,
    img_id: str,
    processing: Union[str],
    processing_kwargs: Mapping[str, Any] = MappingProxyType({}),
    xs: Optional[int] = None,
    ys: Optional[int] = None,
    key_added: Optional[str] = None,
    copy: bool = False,
) -> Union[None, ImageContainer]:
    """
    Process an image.

    Note that crop-wise processing can save memory but may change behaviour of cropping if global statistics are used.
    Leave ``xs`` and ``ys`` as `None` in order to process the full image in one go.

    Parameters
    ----------
    %(img_container)s
    img_id
        Key of image object to process.
    processing
        Name of processing method to use. Available are:

            - `{p.SMOOTH.s!r}`: :func:`skimage.filters.gaussian`.

    processing_kwargs
        Key word arguments to processing method specified by ``processing``.
    %(width_height)s
    key_added
        Key of new image sized array to add into img object. Defaults to ``{{img_id}}_{{processing}}``.
    %(copy_cont)s

    Returns
    -------
    None
        If ``copy = False``: Stores processed image in ``img`` with key ``key_added``.
    :class:`ImageContainer`
        Processed image with key ``key_added``.
    """
    # Note: for processing function that modify the number of channels, need to add a channel_id argument
    processing = Processing(processing)
    img_id_new = img_id + "_" + str(processing) if key_added is None else key_added

    # process crops
    xcoord = []
    ycoord = []
    crops = []
    for crop, x, y in img.generate_equal_crops(xs=xs, ys=ys):
        xcoord.append(x)
        ycoord.append(y)
        if processing == Processing.SMOOTH:
            crops.append(ImageContainer(skimage.filters.gaussian(crop[img_id], **processing_kwargs), img_id=img_id_new))
        else:
            raise NotImplementedError(processing)

    # Reassemble image:
    img_proc = ImageContainer.uncrop_img(crops=crops, x=xcoord, y=ycoord, shape=img.shape)

    if copy:
        return img_proc
    else:
        img.add_img(img=img_proc[img_id_new], img_id=img_id_new)
