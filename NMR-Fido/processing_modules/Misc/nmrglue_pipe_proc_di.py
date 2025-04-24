import nmrglue as ng


def nmrglue_pipe_proc_di_operation(
        dic, data
    ):
    """Delete imaginaries (nmrglue.pipe_proc.di)

    Args:
        dic (dict): Spectrum dictionary.
        data (np.ndarray): N-dimensional array of complex numbers.

    Returns:
        dic (dict), data (np.ndarray): Altered spectrum dictionary and data.
    """
    return ng.pipe_proc.di(dic, data)


#def nmrglue_pipe_proc_ft_widget():
#    return []