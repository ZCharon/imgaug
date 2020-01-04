from __future__ import print_function, division, absolute_import

import sys
# unittest only added in 3.4 self.subTest()
if sys.version_info[0] < 3 or sys.version_info[1] < 4:
    import unittest2 as unittest
else:
    import unittest
# unittest.mock is not available in 2.7 (though unittest2 might contain it?)
try:
    import unittest.mock as mock
except ImportError:
    import mock
import functools

import matplotlib
matplotlib.use('Agg')  # fix execution of tests involving matplotlib on travis
import numpy as np

import PIL.Image

import imgaug as ia
from imgaug import augmenters as iaa
from imgaug import random as iarandom
from imgaug import parameters as iap

# imagecorruptions cannot be installed in <=3.4 due to their
# scikit-image requirement
SUPPORTS_LIBRARY = (sys.version_info[0] == 3 and sys.version_info[1] >= 5)

if SUPPORTS_LIBRARY:
    import imagecorruptions
    from imagecorruptions import corrupt


class Test_get_imgcorrupt_subset(unittest.TestCase):
    @unittest.skipUnless(SUPPORTS_LIBRARY,
                         "imagecorruptions can only be tested for python 3.5+")
    def test_by_comparison_with_imagecorruptions(self):
        subset_names = ["common", "validation", "all"]
        for subset in subset_names:
            with self.subTest(subset=subset):
                func_names, funcs = iaa.imgcorrupt.get_corruption_names(subset)
                func_names_exp = imagecorruptions.get_corruption_names(subset)

                assert func_names == func_names_exp
                for func_name, func in zip(func_names, funcs):
                    assert getattr(
                        iaa.imgcorrupt, "apply_%s" % (func_name,)
                    ) is func

    @unittest.skipUnless(SUPPORTS_LIBRARY,
                         "imagecorruptions can only be tested for python 3.5+")
    def test_subset_functions(self):
        subset_names = ["common", "validation", "all"]
        for subset in subset_names:
            func_names, funcs = iaa.imgcorrupt.get_corruption_names(subset)
            image = np.mod(
                np.arange(32*32*3), 256
            ).reshape((32, 32, 3)).astype(np.uint8)

            for func_name, func in zip(func_names, funcs):
                with self.subTest(subset=subset, name=func_name):
                    # don't verify here whether e.g. only seed 2 produces
                    # different results from seed 1, because some methods
                    # are only dependent on the severity
                    image_aug1 = func(image, severity=5, seed=1)
                    image_aug2 = func(image, severity=5, seed=1)
                    image_aug3 = func(image, severity=1, seed=2)
                    assert not np.array_equal(image, image_aug1)
                    assert not np.array_equal(image, image_aug2)
                    assert not np.array_equal(image_aug2, image_aug3)
                    assert np.array_equal(image_aug1, image_aug2)


class _CompareFuncWithImageCorruptions(unittest.TestCase):
    def _test_by_comparison_with_imagecorruptions(
            self,
            fname,
            shapes=((64, 64), (64, 64, 1), (64, 64, 3)),
            dtypes=("uint8",),
            severities=(1, 2, 3, 4, 5),
            seeds=(1, 2, 3, 4, 5, 6, 7, 8, 9, 10)):
        for shape in shapes:
            for dtype in dtypes:
                for severity in severities:
                    for seed in seeds:
                        with self.subTest(shape=shape, severity=severity,
                                          seed=seed):
                            image_imgaug = self.create_image_imgaug(
                                shape, dtype, 1000 + seed)
                            image_imgcor = np.copy(image_imgaug)

                            self._run_single_comparison_test(
                                fname, image_imgaug, image_imgcor, severity,
                                seed)

    @classmethod
    def create_image_imgaug(cls, shape, dtype, seed, tile=None):
        rng = iarandom.RNG(1000 + seed)

        if dtype.startswith("uint"):
            image = rng.integers(0, 256, size=shape, dtype=dtype)
        else:
            assert dtype.startswith("float")
            image = rng.uniform(0.0, 1.0, size=shape)
            image = image.astype(dtype)

        if tile is not None:
            image = np.tile(image, tile)

        return image

    @classmethod
    def _run_single_comparison_test(cls, fname, image_imgaug, image_imgcor,
                                    severity, seed):
        image_imgaug_sum = np.sum(image_imgaug)
        image_imgcor_sum = np.sum(image_imgcor)

        image_aug, image_aug_exp = cls._generate_augmented_images(
            fname, image_imgaug, image_imgcor, severity, seed)

        # assert that the original image is unchanged,
        # i.e. it was not augmented in-place
        assert np.isclose(np.sum(image_imgcor), image_imgcor_sum, rtol=0,
                          atol=1e-4)
        assert np.isclose(np.sum(image_imgaug), image_imgaug_sum, rtol=0,
                          atol=1e-4)

        # assert that the functions returned numpy arrays and not PIL images
        assert ia.is_np_array(image_aug_exp)
        assert ia.is_np_array(image_aug)

        assert image_aug.shape == image_imgaug.shape
        assert image_aug.dtype.name == image_aug_exp.dtype.name

        atol = 1e-4  # set this to 0.5+1e-4 if output is converted to uint8
        assert np.allclose(image_aug, image_aug_exp, rtol=0, atol=atol)

    @classmethod
    def _generate_augmented_images(cls, fname, image_imgaug, image_imgcor,
                                   severity, seed):
        func_imgaug = getattr(
            iaa.imgcorrupt,
            "apply_%s" % (fname,))
        func_imagecor = functools.partial(corrupt, corruption_name=fname)

        with iarandom.temporary_numpy_seed(seed):
            image_aug_exp = func_imagecor(image_imgcor, severity=severity)
            if not ia.is_np_array(image_aug_exp):
                image_aug_exp = np.asarray(image_aug_exp)
            if image_imgcor.ndim == 2:
                image_aug_exp = image_aug_exp[:, :, 0]
            elif image_imgcor.shape[-1] == 1:
                image_aug_exp = image_aug_exp[:, :, 0:1]

        image_aug = func_imgaug(image_imgaug, severity=severity,
                                seed=seed)

        return image_aug, image_aug_exp


@unittest.skipUnless(SUPPORTS_LIBRARY,
                     "imagecorruptions can only be tested for python 3.5+")
class Test_apply_functions(_CompareFuncWithImageCorruptions):
    def test_apply_imgcorrupt_gaussian_noise(self):
        self._test_by_comparison_with_imagecorruptions("gaussian_noise")

    def test_apply_imgcorrupt_shot_noise(self):
        self._test_by_comparison_with_imagecorruptions("shot_noise")

    def test_apply_imgcorrupt_impulse_noise(self):
        self._test_by_comparison_with_imagecorruptions("impulse_noise")

    def test_apply_imgcorrupt_speckle_noise(self):
        self._test_by_comparison_with_imagecorruptions("speckle_noise")

    def test_apply_imgcorrupt_gaussian_blur(self):
        self._test_by_comparison_with_imagecorruptions("gaussian_blur")

    def test_apply_imgcorrupt_glass_blur(self):
        # glass_blur() is extremely slow, so we run only a reduced set
        # of tests here
        self._test_by_comparison_with_imagecorruptions(
            "glass_blur",
            shapes=[(32, 32), (32, 32, 1), (32, 32, 3)],
            severities=[3],
            seeds=[1])

    def test_apply_imgcorrupt_defocus_blur(self):
        self._test_by_comparison_with_imagecorruptions(
            "defocus_blur")

    def test_apply_imgcorrupt_motion_blur(self):
        self._test_by_comparison_with_imagecorruptions(
            "motion_blur")

    def test_apply_imgcorrupt_zoom_blur(self):
        self._test_by_comparison_with_imagecorruptions(
            "zoom_blur")

    def test_apply_imgcorrupt_fog(self):
        self._test_by_comparison_with_imagecorruptions(
            "fog")

    def test_apply_imgcorrupt_frost(self):
        self._test_by_comparison_with_imagecorruptions(
            "frost",
            severities=[1, 5],
            seeds=[1, 5, 10])

    def test_apply_imgcorrupt_snow(self):
        self._test_by_comparison_with_imagecorruptions(
            "snow")

    def test_apply_imgcorrupt_spatter(self):
        self._test_by_comparison_with_imagecorruptions(
            "spatter")

    def test_apply_imgcorrupt_contrast(self):
        self._test_by_comparison_with_imagecorruptions("contrast")

    def test_apply_imgcorrupt_brightness(self):
        self._test_by_comparison_with_imagecorruptions("brightness")

    def test_apply_imgcorrupt_saturate(self):
        self._test_by_comparison_with_imagecorruptions(
            "saturate")

    def test_apply_imgcorrupt_jpeg_compression(self):
        self._test_by_comparison_with_imagecorruptions(
            "jpeg_compression")

    def test_apply_imgcorrupt_pixelate(self):
        self._test_by_comparison_with_imagecorruptions(
            "pixelate")

    def test_apply_imgcorrupt_elastic_transform(self):
        self._test_by_comparison_with_imagecorruptions(
            "elastic_transform")


@unittest.skipUnless(SUPPORTS_LIBRARY,
                     "imagecorruptions can only be tested for python 3.5+")
class TestAugmenters(unittest.TestCase):
    def _test_augmenter(self, augmenter_name, func_expected,
                        dependent_on_seed):
        severity = 5
        aug_cls = getattr(iaa.imgcorrupt, augmenter_name)
        image = np.mod(
            np.arange(32*32*3), 256
        ).reshape((32, 32, 3)).astype(np.uint8)

        rng = iarandom.RNG(1)
        # replay sampling of severities, not really necessary here as we
        # use a deterministic value, but still done for good style
        _ = iap.Deterministic(1).draw_samples((1,), rng)

        # As for the functions above, we can't just change the seed value
        # to get different augmentations as many functions are dependend
        # only on the severity. So we change only for some functions only
        # the seed and for the others severity+seed.
        image_aug1 = aug_cls(severity=severity, random_state=1)(image=image)
        image_aug2 = aug_cls(severity=severity, random_state=1)(image=image)
        if dependent_on_seed:
            image_aug3 = aug_cls(severity=severity, random_state=2)(
                image=image)
        else:
            image_aug3 = aug_cls(severity=severity-1, random_state=2)(
                image=image)
        image_aug_exp = func_expected(
            image,
            severity=severity,
            seed=rng.generate_seed_())

        assert aug_cls(severity=severity).func is func_expected
        assert np.array_equal(image_aug1, image_aug_exp)
        assert np.array_equal(image_aug2, image_aug_exp)
        assert not np.array_equal(image_aug3, image_aug2)

    def test_gaussian_noise(self):
        self._test_augmenter("GaussianNoise",
                             iaa.imgcorrupt.apply_gaussian_noise,
                             True)

    def test_shot_noise(self):
        self._test_augmenter("ShotNoise",
                             iaa.imgcorrupt.apply_shot_noise,
                             True)

    def test_impulse_noise(self):
        self._test_augmenter("ImpulseNoise",
                             iaa.imgcorrupt.apply_impulse_noise,
                             True)

    def test_speckle_noise(self):
        self._test_augmenter("SpeckleNoise",
                             iaa.imgcorrupt.apply_speckle_noise,
                             True)

    def test_gaussian_blur(self):
        self._test_augmenter("GaussianBlur",
                             iaa.imgcorrupt.apply_gaussian_blur,
                             False)

    def test_glass_blur(self):
        self._test_augmenter("GlassBlur",
                             iaa.imgcorrupt.apply_glass_blur,
                             False)

    def test_defocus_blur(self):
        self._test_augmenter("DefocusBlur",
                             iaa.imgcorrupt.apply_defocus_blur,
                             False)

    def test_motion_blur(self):
        self._test_augmenter("MotionBlur",
                             iaa.imgcorrupt.apply_motion_blur,
                             False)

    def test_zoom_blur(self):
        self._test_augmenter("ZoomBlur",
                             iaa.imgcorrupt.apply_zoom_blur,
                             False)

    def test_fog(self):
        self._test_augmenter("Fog",
                             iaa.imgcorrupt.apply_fog,
                             True)

    def test_frost(self):
        self._test_augmenter("Frost",
                             iaa.imgcorrupt.apply_frost,
                             False)

    def test_snow(self):
        self._test_augmenter("Snow",
                             iaa.imgcorrupt.apply_snow,
                             True)

    def test_spatter(self):
        self._test_augmenter("Spatter",
                             iaa.imgcorrupt.apply_spatter,
                             True)

    def test_contrast(self):
        self._test_augmenter("Contrast",
                             iaa.imgcorrupt.apply_contrast,
                             False)

    def test_brightness(self):
        self._test_augmenter("Brightness",
                             iaa.imgcorrupt.apply_brightness,
                             False)

    def test_saturate(self):
        self._test_augmenter("Saturate",
                             iaa.imgcorrupt.apply_saturate,
                             False)

    def test_jpeg_compression(self):
        self._test_augmenter("JpegCompression",
                             iaa.imgcorrupt.apply_jpeg_compression,
                             False)

    def test_pixelate(self):
        self._test_augmenter("Pixelate",
                             iaa.imgcorrupt.apply_pixelate,
                             False)

    def test_elastic_transform(self):
        self._test_augmenter("ElasticTransform",
                             iaa.imgcorrupt.apply_elastic_transform,
                             True)

