import nmrglue as ng


def nmrglue_pipe_proc_tp_operation(
        dic, data,
        hyper=False,
        nohyper=False,
        auto=False,
        nohdr=False
    ):
    """Transpose (nmrglue.pipe_proc.tp)

    Args:
        dic (dict): Spectrum dictionary.
        data (np.ndarray): N-dimensional array of complex numbers.
        hyper (bool): Desc.
        nohyper (bool): Desc.
        auto (bool): Choose mode automatically.
        nohdr (bool): Desc

    Returns:
        dic (dict), data (np.ndarray): Altered spectrum dictionary and data.
    """
    return ng.pipe_proc.tp(dic, data, hyper, nohyper, auto, nohdr)