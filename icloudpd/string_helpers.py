"""String helper functions"""


def truncate_middle(string, length):
    """Truncates a string to a maximum length, inserting "..." in the middle"""
    if len(string) <= length:
        return string
    if length < 0:
        raise ValueError("n must be greater than or equal to 1")
    if length <= 3:
        return "..."[0:length]
    end_length = int(length) // 2 - 2
    start_length = length - end_length - 4
    if end_length < 1:
        end_length = 1
    return "{0}...{1}".format(string[:start_length], string[-end_length:])
