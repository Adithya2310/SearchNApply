class _Unknown:
    def __repr__(self):
        return "UNKNOWN"

    def __bool__(self):
        raise TypeError("UNKNOWN has no truthiness — compare with `is UNKNOWN` instead")


# Sentinel distinguishing "this dimension has no information" from any real
# score, including 0.0. Compare with `is UNKNOWN`, never `==`.
UNKNOWN = _Unknown()
