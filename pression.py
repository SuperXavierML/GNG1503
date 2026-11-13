class Pression:
    """Une lecture : pression artérielle (mmHg) et pouls (bpm)."""

    def __init__(self, systolique, diastolique, pouls):
        self.systolique = systolique
        self.diastolique = diastolique
        self.pouls = pouls

    def pulsee(self):
        """Pression pulsée = systolique - diastolique."""
        return self.systolique - self.diastolique

