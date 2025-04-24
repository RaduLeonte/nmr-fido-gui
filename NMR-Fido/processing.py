'''Processing'''

import numpy as np
import nmrglue as ng
#import matplotlib.pyplot as plt

'''
Window functions
'''

def sine_bell(data: np.ndarray, power: float=2.0, start: float=0.5, end: float=1) -> np.ndarray:
    '''
    Applies sine-bell window function (nmrPipe) to given data.
    
    Parameters
    ----------
    data: np.ndarray
        n-dimensional array of complex numbers
    power: float
        power to raise sine function by
    start: float
        starting offset? [0, 1]
    end: float
        ending offset? (-start, 1]

    Returns
    -------
    ndarray
        apodized data
        
    Raises
    ------
    ValueError
        when start and end offsets are outside their allowed ranges
    '''
    
    print("Stub function called: sine_bell")
    return None


def lorentz_to_gaussian(data: np.ndarray) -> np.ndarray:
    '''
    Applies lorentz-to-gaussian window function (nmrPipe) to given data.
    
    Parameters
    ----------
    data: np.ndarray
        n-dimensional array of complex numbers

    Returns
    -------
    ndarray
        apodized data
    '''
    
    print("Stub function called: lorentz_to_gaussian")
    return None


def exponential_multiply(data: np.ndarray) -> np.ndarray:
    '''
    Applies exponential multiply window function to given data.
    
    Parameters
    ----------
    data: np.ndarray
        n-dimensional array of complex numbers

    Returns
    -------
    ndarray
        apodized data
    '''
    
    print("Stub function called: exponential_multiply")
    return None


def squared_sine(data: np.ndarray) -> np.ndarray:
    '''
    Applies squared sine window function to given data.
    
    Parameters
    ----------
    data: np.ndarray
        n-dimensional array of complex numbers

    Returns
    -------
    ndarray
        apodized data
    '''
    
    print("Stub function called: squared_sine")
    return None


'''
Processing
'''

def fourier_transform(dic, data: np.ndarray) -> np.ndarray:
    '''
    Complex fourier transform.
    
    Parameters
    ----------
    data: np.ndarray
        n-dimensional array of complex numbers

    Returns
    -------
    ndarray
        fourier transformed data
    '''
    
    return dic, np.apply_along_axis(
        lambda fid: np.fft.fftshift(np.fft.ifft(fid)),
        1,
        data
    )


def zero_fill(dic, data: np.ndarray, multiplier: int=2, final_size: int=None, pad: int=None) -> np.ndarray:
    '''
    Fills data with zeroes.
    
    Parameters
    ----------
    data: np.ndarray
        n-dimensional array of complex numbers
    multiplier: int
        input data will be filled so the final size will me len(data)*multiplier
    final_size: int
        input data will be filled until the data's length equals this argument
    pad: int
        [pad] many zeroes will be added to the end of the data

    Returns
    -------
    ndarray
        zero-filled data
        
    Raises
    ------
    ValueError
        when multiple filling modes are specified
    '''
    return dic, np.concatenate(
        (
            data,
            np.zeros(data.shape, dtype=np.complex64) # complex128?
        ),
        axis=1
    )


def phase_correction(dic, data: np.ndarray, p0: float=0.0, p1: float=0.0, pivot: int=0) -> np.ndarray:
    '''
    Adjusts phase of data d(f).
    f' = f * exp( -i*(p0 + p1*(f-pivot)))
    
    Parameters
    ----------
    data: np.ndarray
        n-dimensional array of complex numbers
    p0: float
        Zero-th order phase correction term in degrees.
    p1: float
        First order phase correction term in degrees.
    pivot: int
        Position of "pivot" for first order correction.
        At this point, p1 does not affect the phase.

    Returns
    -------
    ndarray
        phase-corrected data
    '''
    
    first_order_correction = np.radians(p1)*((np.arange(data.shape[-1]) - pivot)/data.shape[-1])
    phase_correction = np.exp(1.0j * (np.radians(p0) + first_order_correction))
    
    return dic, phase_correction * data


def baseline_correction(data: np.ndarray) -> np.ndarray:
    '''
    Polynomial baseline correction (nmrPipe).
    
    Parameters
    ----------
    data: np.ndarray
        n-dimensional array of complex numbers
    
    Returns
    -------
    ndarray
        baseline corrected data
    '''
    
    print("Stub function called: baseline_correction")
    return None


'''
Miscellaneous
'''

def transpose(dic, data: np.ndarray) -> np.ndarray:
    '''
    Transposes data.
    
    Parameters
    ----------
    data: np.ndarray
        n-dimensional array of complex numbers

    Returns
    -------
    ndarray
        transposed data
    '''
    
    return dic, data.transpose()


def crop_data(data: np.ndarray) -> np.ndarray:
    '''
    Crops data.
    
    Parameters
    ----------
    data: np.ndarray
        n-dimensional array of complex numbers

    Returns
    -------
    ndarray
        cropped data
    '''
    
    print("Stub function called: crop_data")
    return None


def solvent_filter(data: np.ndarray) -> np.ndarray:
    '''
    Applies solvent filter.
    
    Parameters
    ----------
    data: np.ndarray
        n-dimensional array of complex numbers

    Returns
    -------
    ndarray
        data with solvent filter applied
    '''
    
    print("Stub function called: solvent_filter")
    return None


def linear_prediction(data: np.ndarray) -> np.ndarray:
    '''
    Linear prediction.
    
    Parameters
    ----------
    data: np.ndarray
        n-dimensional array of complex numbers

    Returns
    -------
    ndarray
        data with linearly predicted points added
    '''
    
    print("Stub function called: linear_prediction")
    return None


def hilbert_transform(data: np.ndarray) -> np.ndarray:
    '''
    Reconstruct imaginary data using hilbert transform.
    
    Parameters
    ----------
    data: np.ndarray
        n-dimensional array of real numbers

    Returns
    -------
    ndarray
        array of complex numbers
    '''
    
    print("Stub function called: hilbert_transform")
    return None


def add_constant(data: np.ndarray, constant: complex) -> np.ndarray:
    '''
    Add a constant to every point.
    
    Parameters
    ----------
    data: np.ndarray
        n-dimensional array of real numbers
    constant: complex
        complex number to add

    Returns
    -------
    ndarray
        data with constant added
    '''
    
    print("Stub function called: add_constant")
    return None


def multiply_constant(data: np.ndarray, constant: complex) -> np.ndarray:
    '''
    Multiply every point by a constant.
    
    Parameters
    ----------
    data: np.ndarray
        n-dimensional array of real numbers
    constant: complex
        complex number to multiply data by

    Returns
    -------
    ndarray
        data with constant added
    '''
    
    print("Stub function called: multiply_constant")
    return None


if __name__ == "__main__":
    dic, data =  ng.pipe.read("src/test.fid")
    
    fig, axs = plt.subplots(4)
    phases = [
        [[0.0, 0.0, 0], [0.0, 0.0, 0]],
        [[-180.0, 0.0, 0], [0.0, 0.0, 0]],
        [[-180.0, -180, 1461], [0.0, 0.0, 0]]
    ]
    for i in range(3):
        pdata = zero_fill(data)
        pdata = fourier_transform(pdata)
        pdata = phase_correction(pdata, *phases[i][0])
        # delete imaginaries
        
        pdata = transpose(pdata)
        
        pdata = zero_fill(pdata)
        pdata = fourier_transform(pdata)
        pdata = phase_correction(pdata, *phases[i][1])
        # delete imaginaries
        
        pdata = transpose(pdata)
        axs[i].plot(pdata[332])
        axs[i].set_xlim([1425, 1550])


    axs[3].imshow(np.real(pdata)*-1)
    plt.show()