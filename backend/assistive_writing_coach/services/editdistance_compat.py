try:
    import editdistance
except ImportError:
    import Levenshtein

    class _EditDistance:
        @staticmethod
        def eval(a, b):
            return Levenshtein.distance(a, b)

    editdistance = _EditDistance()
