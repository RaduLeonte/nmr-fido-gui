import nmrglue as ng


def nmrglue_pipe_proc_ft_operation(
        dic, data,
        auto=False,
        real=False,
        inv=False,
        alt=False,
        neg=False,
        null=False,
        bruk=False,
        debug=False
    ):
    """Fourier transform (nmrglue.pipe_proc.ft)

    Args:
        dic (dict): Spectrum dictionary.
        data (np.ndarray): N-dimensional array of complex numbers.
        auto (bool): Choose mode automatically.
        real (bool): Data is composed only of real numbers.
        inv (bool): Inverse fourier transform.
        alt (bool): Use sign alternation. Every other point will have its sign flipped.
        neg (bool): Negate imaginary values.
        null (bool): Update the spectrum dictionary but do not alter data.
        bruk (bool): Data is Redfield sequential. Equivalent to: alt=True, real=True.
        debug (bool): Print nmrglue debug info.

    Returns:
        dic (dict), data (np.ndarray): Altered spectrum dictionary and data.
    """
    return ng.pipe_proc.ft(dic, data, auto, real, inv, alt, neg, null, bruk, debug)


#def nmrglue_pipe_proc_ft_widget():
#    return []