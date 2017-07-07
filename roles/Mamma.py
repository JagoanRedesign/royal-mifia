from .Role import Role
import strings as s
import random

class Mamma(Role):
    """La mamma sente i pettegolezzi in giro per la città e inizia conoscendo un ruolo a caso..."""
    icon = s.mom_icon
    team = 'Good'
    name = s.mom_name
    powerdesc = s.mom_power_description
    value = 25

    def __repr__(self) -> str:
        return "<Role: Mamma>"

    def onstartgame(self, bot, game):
        # Scegli un bersaglio casuale che non sia il giocatore stesso
        possibletargets = game.players.copy()
        possibletargets.pop(self.player)
        target = random.sample(possibletargets, 1)[0]
        self.player.message(bot, s.mom_discovery.format(target=target.tusername,
                                                            icon=target.role.icon,
                                                            role=target.role.name))