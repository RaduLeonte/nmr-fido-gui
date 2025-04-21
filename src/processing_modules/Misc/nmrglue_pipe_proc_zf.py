import nmrglue as ng


def nmrglue_pipe_proc_zf_operation(
        dic, data,
        zf=1,
        pad="auto",
        size="auto",
        mid=False,
        inter=False,
        auto=False,
        inv=False
    ):
    """Zero filling (nmrglue.pipe_proc.zf)

    Args:
        dic (dict): Spectrum dictionary.
        data (np.ndarray): N-dimensional array of complex numbers.
        zf (int): Desc.
        pad (str): Desc.
        size (str): Desc.
        mid (bool): Desc.
        inter (bool): Desc.
        auto (bool): Choose mode automatically.

    Returns:
        dic (dict), data (np.ndarray): Altered spectrum dictionary and data.
    """
    return ng.pipe_proc.zf(dic, data, zf, pad, size, mid, inter, auto, inv)