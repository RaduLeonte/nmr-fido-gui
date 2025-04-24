import nmrglue as ng


def nmrglue_pipe_proc_sp_operation(
        dic, data,
        off=0.0,
        end=1.0,
        pow=1.0,
        c=1.0,
        start=1,
        size='default',
        inv=False,
        one=False,
        hdr=False
    ):
    """Sine bell (nmrglue.pipe_proc.sp)

    Args:
        dic (dict): Spectrum dictionary.
        data (np.ndarray): N-dimensional array of complex numbers.
        off (float): Desc.
        end (float): Desc.
        pow (float): Desc.
        c (float): Desc.
        start (int): Desc.
        size (str): Desc.
        inv (bool): Desc.
        one (bool): Desc.
        hdr (bool): Desc.

    Returns:
        dic (dict), data (np.ndarray): Altered spectrum dictionary and data.
    """
    return ng.pipe_proc.sp(dic, data, off, end, pow, c, start, size, inv, one, hdr)