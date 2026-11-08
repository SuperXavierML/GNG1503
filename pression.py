class Pression:

    def __init__(self, systolique, diastolique, pouls):
        self.systolique = systolique
        self.diastolique = diastolique
        self.pouls = pouls

    def pulsee(self):
        return (self.systolique-self.diastolique)
