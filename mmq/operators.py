#!/usr/bin/env python3

"""A module that implement high level interface to manipulate linear operators. This
module is not required but can serve as guide or for reuse.

"""

import abc

from typing import Tuple

import numpy as np


def dft2(obj):
    """Return the orthogonal real 2D fft

    Parameters
    ----------
    obj : array-like
      The array on which to perform the 2D DFT

    Notes
    -----
    This function is a wrapper of numpy.fft.rfft2
    """
    return np.fft.rfft2(obj, norm="ortho")


def idft2(obj, shape):
    """Return the orthogonal real 2D ifft

    Parameters
    ----------
    obj : array-like
      The array on which to perform the inverse 2D DFT

    shape
    -----
      The output shape

    Notes
    -----
    This function is a wrapper of numpy.fft.irfft2
    """
    return np.fft.irfft2(obj, norm="ortho", s=shape)


class Operator(abc.ABC):
    """An abstract base class for linear operators"""

    @abc.abstractmethod
    def forward(self, point):
        """Return H·x"""
        return NotImplemented

    @abc.abstractmethod
    def adjoint(self, point):
        """Return Hᵗ·e"""
        return NotImplemented

    def fwback(self, point):
        """Return HᵗH·x"""
        return self.backward(self.forward(point))

    def backward(self, point):
        """Return Hᵗ·e"""
        return self.adjoint(point)

    def transpose(self, point):
        """Return Hᵗ·e"""
        return self.adjoint(point)

    def T(self, point):
        """Return Hᵗ·e"""
        return self.adjoint(point)

    def __call__(self, point):
        """Return H·x"""
        return self.forward(point)


class Conv2(Operator):
    """The 2D convolution on image

    Does not suppose periodic or circular condition.

    Notes
    -----
    Use the fft internaly for fast implementation.

    """

    def __init__(self, ir, shape):
        """The 2D convolution on image

        Does not suppose periodic or circular condition.
        """

        self.imp_resp = ir
        self.shape = shape
        self.ir_shape = ir.shape
        self.freq_resp = ir2fr(ir, self.shape)

    def forward(self, point):
        return idft2(dft2(point) * self.freq_resp, self.shape)[
            : -self.ir_shape[0], : -self.ir_shape[1]
        ]

    def adjoint(self, point):
        out = np.zeros(self.shape)
        out[: point.shape[0], : point.shape[1]] = point
        return idft2(dft2(out) * self.freq_resp.conj(), self.shape)

    def fwback(self, point):
        out = idft2(dft2(point) * self.freq_resp, self.shape)
        out[-self.ir_shape[0] :, :] = 0
        out[:, -self.ir_shape[1] :] = 0
        return idft2(dft2(out) * self.freq_resp.conj(), self.shape)


class Diff(Operator):
    """The difference operator

    The first order differences along an axis

    Attributes
    ----------
    axis : int
        The axis along which the differences is performed

    Notes
    -----
    Use `numpy.diff` internaly and implement the correct adjoint, with
    `numpy.diff` also.

    """

    def __init__(self, axis):
        """The difference operator

        The first order differences along an axis

        Parameters
        ----------
        axis: int
            the axis along which to perform the diff"""
        self.axis = axis

    def response(self, ndim):
        """Return the equivalent impulsionnal response.

        The result of `forward` method is equivalent with the 'valid'
        convolution with this response.

        The adjoint operator corresponds the the 'full' convolution with flipped
        response.

        """
        ir = np.zeros(ndim * [2])
        index = ndim * [0]
        index[self.axis] = slice(None, None)
        ir[tuple(index)] = [1, -1]
        return ir

    def freq_response(self, ndim, shape):
        """The equivalent frequency response IF circular hypothesis is considered"""
        return ir2fr(self.response(ndim), shape)

    def forward(self, point):
        return np.diff(point, axis=self.axis)

    def adjoint(self, point):
        return -np.diff(point, prepend=0, append=0, axis=self.axis)


def ir2fr(imp_resp, shape: Tuple, center=None, real=True):
    """Return the frequency response from impulsionnal responses

    This function make the necessary correct zero-padding, zero convention,
    correct DFT etc. to compute the frequency response from impulsionnal
    responses (IR).

    The IR array is supposed to have the origin in the middle of the array.

    The Fourier transform is performed on the last `len(shape)` dimensions.

    Parameters
    ----------
    imp\_resp : np.ndarray
      The impulsionnal responses.

    shape : tuple of int
      A tuple of integer corresponding to the target shape of the frequency
      responses, without hermitian property. `len(shape) >= ndarray.ndim`. The
      DFT is performed on the `len(shape)` last axis of ndarray.

    center : tuple of int, optional
      The origin index of the impulsionnal response. The middle by default.

    real : boolean, optionnal
      If True, imp_resp is supposed real, the hermissian property is used with
      rfftn DFT and the output has `shape[-1] / 2 + 1` elements on the last
      axis.

    Returns
    -------
    y : np.ndarray

      The frequency responses of shape `shape` on the last `len(shape)`
      dimensions.

    Notes
    -----

    - The output is returned as C-contiguous array.

    - For convolution, the result have to be used with unitary discrete Fourier
      transform for the signal (norm="ortho" of fft).

    - DFT are always peformed on last axis for efficiency (C-order array).

    """
    if len(shape) > imp_resp.ndim:
        raise ValueError("length of shape must be inferior to imp_resp.ndim")

    if not center:
        center = [int(np.floor(length / 2)) for length in imp_resp.shape[-len(shape) :]]

    if len(center) != len(shape):
        raise ValueError("center and shape must have the same length")

    # Place the provided IR at the beginning of the array
    irpadded = np.zeros(imp_resp.shape[: -len(shape)] + shape)
    irpadded[tuple([slice(0, s) for s in imp_resp.shape])] = imp_resp

    # Roll, or circshift to place the origin at index 0, the
    # hypothesis of the DFT
    for axe, shift in enumerate(center):
        irpadded = np.roll(irpadded, -shift, imp_resp.ndim - len(shape) + axe)

    # Perform the DFT on the last axes
    if real:
        freq_resp = np.ascontiguousarray(
            np.fft.rfftn(
                irpadded, axes=list(range(imp_resp.ndim - len(shape), imp_resp.ndim))
            )
        )
    else:
        freq_resp = np.ascontiguousarray(
            np.fft.fftn(
                irpadded, axes=list(range(imp_resp.ndim - len(shape), imp_resp.ndim))
            )
        )
    return freq_resp