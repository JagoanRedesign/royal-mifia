#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from telegram.ext import Updater
import filemanager

import logging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

token = filemanager.readfile('telegramapi.txt')
updater = Updater(token)


# Ruoli possibili per i giocatori
# Base di un ruolo
class Role:
    icon = "-"
    team = 'None'  # Squadra: 'None', 'Good', 'Evil'
    name = "UNDEFINED"
    haspower = False
    poweruses = 0

    def power(self, bot, game, player, arg):
        pass

    def onendday(self, bot, game):
        pass


class Royal(Role):
    icon = "\U0001F610"
    team = 'Good'
    name = "Royal"


class Mifioso(Role):
    icon = "\U0001F47F"
    team = 'Evil'
    target = None
    name = "Mifioso"

    def power(self, bot, game, player, arg):
        # Imposta qualcuno come bersaglio
        self.target = game.findplayerbyusername(arg)
        player.message(bot, "Hai selezionato come bersaglio {0}.".format(self.target.tusername))

    def onendday(self, bot, game):
        # Uccidi il bersaglio
        if self.target is not None:
            self.target.kill()
            game.message(bot, "{0} è stato ucciso dalla Mifia.\n"
                              "Era un {1} {2}."
                              .format(self.target.tusername, self.target.role.icon, self.target.role.name))


class Investigatore(Role):
    icon = "\U0001F575"
    team = 'Good'
    poweruses = 1
    name = "Investigatore"

    def power(self, bot, game, player, arg):
        if self.poweruses > 0:
            target = game.findplayerbyusername(arg)
            if target is not None:
                self.poweruses -= 1
                player.message(bot, "{0} è un {1} {2}.\n"
                                    "Puoi usare il tuo potere ancora {3} volte oggi."
                                    .format(target.tusername, target.role.icon, target.role.name, self.poweruses))
            else:
                player.message(bot, "Il nome utente specificato non esiste.")
        else:
            player.message(bot, "Non puoi più usare il tuo potere oggi.")

    def onendday(self, bot, game):
        # Ripristina il potere
        self.poweruses = 1


# Classi per i giocatori
class Player:
    tid = int()
    tusername = str()
    role = Role()  # Di base, ogni giocatore è un ruolo indefinito
    alive = True
    votingfor = None  # Diventa un player se ha votato
    votes = 0  # Voti. Aggiornato da updatevotes()

    def message(self, bot, text):
        bot.sendMessage(self.tid, text)

    def kill(self):
        self.alive = False

    def __init__(self, tid, tusername):
        self.tid = tid
        self.tusername = tusername


# Classe di ogni partita
class Game:
    adminid = int()
    groupid = int()
    players = list()
    tokill = list()  # Giocatori che verranno uccisi all'endday
    phase = 'Join'  # Fase di gioco: 'Join', 'Voting', 'Ended'

    def __init__(self, groupid, adminid):
        self.groupid = groupid
        self.adminid = adminid

    def message(self, bot, text):
        bot.sendMessage(self.groupid, text)

    def adminmessage(self, bot, text):
        bot.sendMessage(self.adminid, text)

    def mifiamessage(self, bot, text):
        # Trova tutti i mifiosi nell'elenco dei giocatori
        for player in self.players:
            if isinstance(player.role, Mifioso):
                player.message(bot, text)
        # Inoltra il messaggio all'admin
        self.adminmessage(bot, text)

    def findplayerbyid(self, tid) -> Player:
        # Trova tutti i giocatori con un certo id
        for player in self.players:
            if player.tid == tid:
                return player
        else:
            return None

    def findplayerbyusername(self, tusername) -> Player:
        # Trova tutti i giocatori con un certo username
        for player in self.players:
            if player.tusername.lower() == tusername.lower():
                return player
        else:
            return None

    def assignroles(self, bot, mifia=0, investigatore=0):
        import random
        random.seed()
        playersleft = self.players.copy()
        random.shuffle(playersleft)
        # Seleziona mifiosi
        while mifia > 0:
            try:
                selected = playersleft.pop()
            except IndexError:
                raise IndexError("Non ci sono abbastanza giocatori!")
            else:
                selected.role = Mifioso()
                mifia -= 1
        # Seleziona detective
        while investigatore > 0:
            try:
                selected = playersleft.pop()
            except IndexError:
                raise IndexError("Non ci sono abbastanza giocatori!")
            else:
                selected.role = Investigatore()
                investigatore -= 1
        # Assegna il ruolo di Royal a tutti gli altri
        for player in playersleft:
            player.role = Royal()
        # Manda i ruoli assegnati a tutti
        for player in self.players:
            player.message(bot, "Ti è stato assegnato il ruolo di {0} {1}.".format(player.role.icon, player.role.name))

    def updatevotes(self):
        for player in self.players:
            player.votes = 0
        for player in self.players:
            if player.votingfor is not None:
                player.votingfor.votes += 1

    def mostvotedplayer(self) -> Player:
        mostvoted = None
        self.updatevotes()
        for player in self.players:
            # Temo di aver fatto un disastro. Ma finchè va...
            if mostvoted is None and player.votes == 0:
                pass
            elif (mostvoted is None and player.votes >= 1) or (player.votes > mostvoted.votes):
                mostvoted = player
            elif mostvoted is not None and player.votes == mostvoted.votes:
                # Non sono sicuro che questo algoritmo sia effettivamente il più equo. Ma vabbè, non succederà mai
                import random
                mostvoted = random.choice([player, mostvoted])
        return mostvoted

    def endday(self, bot):
        # TODO: Per mettere l'angelo bisogna dare una priorità a ogni ruolo.
        for player in self.players:
            player.role.onendday(bot, self)
        lynched = self.mostvotedplayer()
        if lynched is not None:
            self.message(bot, "{0} era il più votato ed è stato ucciso dai Royal.\n"
                              "Era un {1} {2}.".format(lynched.tusername, lynched.role.icon, lynched.role.name))
            lynched.kill()
        else:
            self.message(bot, "La Royal Games non è giunta a una decisione in questo giorno e non ha ucciso nessuno.")
        for player in self.players:
            player.votingfor = None
        # Condizioni di vittoria
        royal = 0
        mifiosi = 0
        for player in self.players:
            if player.alive and isinstance(player.role, Mifioso):
                mifiosi += 1
            elif player.alive and (isinstance(player.role, Royal) or isinstance(player.role, Investigatore)):
                royal += 1
        if mifiosi >= royal:
            self.message(bot, "I Mifiosi rimasti sono più dei Royal.\n"
                              "La Mifia vince!")
            self.endgame()
        elif mifiosi == 0:
            self.message(bot, "Tutti i Mifiosi sono stati eliminati.\n"
                              "La Royal Games vince!")
            self.endgame()

    def endgame(self):
        inprogress.remove(self)

# Partite in corso
inprogress = list()


# Trova una partita con un certo id
def findgamebyid(gid) -> Game:
    for game in inprogress:
        if game.groupid == gid:
            return game


# Comandi a cui risponde il bot
def ping(bot, update):
    bot.sendMessage(update.message.chat['id'], "Pong!")


def newgame(bot, update):
    if update.message.chat['type'] != 'private':
        g = Game(update.message.chat['id'], update.message.from_user['id'])
        inprogress.append(g)
        bot.sendMessage(update.message.chat['id'], "Partita creata: " + repr(g))
    else:
        bot.sendMessage(update.message.chat['id'], "Non puoi creare una partita in questo tipo di chat!")


def join(bot, update):
    game = findgamebyid(update.message.chat['id'])
    if game is not None:
        if game.phase == 'Join':
            p = game.findplayerbyid(update.message.from_user['id'])
            if p is None:
                p = Player(update.message.from_user['id'], update.message.from_user['username'])
                game.players.append(p)
                bot.sendMessage(update.message.chat['id'], "Unito alla partita: " + repr(p))
            else:
                bot.sendMessage(update.message.chat['id'], "Ti sei già unito alla partita: " + repr(p))


def debug(bot, update):
    game = findgamebyid(update.message.chat['id'])
    if game is None:
        bot.sendMessage(update.message.chat['id'], "In questo gruppo non ci sono partite in corso.")
    else:
        if game.adminid == update.message.from_user['id']:
            text = "Gruppo: {0}\n" \
                   "Creatore: {1}\n" \
                   "Fase: {2}\n" \
                   "Giocatori partecipanti:\n".format(game.groupid, game.adminid, game.phase)
            game.updatevotes()
            # Aggiungi l'elenco dei giocatori
            for player in game.players:
                if not player.alive:
                    text += "\U0001F480 {0}\n".format(player.tusername)
                elif player.votingfor is not None:
                    text += "{0} {1} ({2}) vota per {3}\n"\
                            .format(player.role.icon, player.tusername, player.votes, player.votingfor.tusername)
                else:
                    text += "{0} {1} ({2})\n".format(player.role.icon, player.tusername, player.votes)
            bot.sendMessage(update.message.from_user['id'], text)


def status(bot, update):
    game = findgamebyid(update.message.chat['id'])
    if game is None:
        bot.sendMessage(update.message.chat['id'], "In questo gruppo non ci sono partite in corso.")
    else:
        text = "Gruppo: {0}\n" \
               "Creatore: {1}\n" \
               "Fase: {2}\n" \
               "Giocatori partecipanti:\n".format(game.groupid, game.adminid, game.phase)
        game.updatevotes()
        # Aggiungi l'elenco dei giocatori
        for player in game.players:
            if not player.alive:
                text += "\U0001F480 {0}\n".format(player.tusername)
            elif player.votingfor is not None:
                text += "\U0001F610 {0} ({1}) vota per {2}\n"\
                        .format(player.tusername, player.votes, player.votingfor.tusername)
            else:
                text += "\U0001F610 {0} ({1})\n".format(player.tusername, player.votes)
        bot.sendMessage(update.message.chat['id'], text)


def endjoin(bot, update):
    game = findgamebyid(update.message.chat['id'])
    if game is not None and game.phase is 'Join' and update.message.from_user['id'] == game.adminid:
        game.phase = 'Voting'
        bot.sendMessage(update.message.chat['id'], "La fase di join è terminata.")
        game.assignroles(bot, mifia=2, investigatore=1)
        bot.sendMessage(update.message.chat['id'], "I ruoli sono stati assegnati.\n"
                                                   "Controlla la chat con @mifiabot.")


def vote(bot, update):
    game = findgamebyid(update.message.chat['id'])
    if game is not None and game.phase is 'Voting':
        player = game.findplayerbyid(update.message.from_user['id'])
        if player is not None and player.alive:
            target = game.findplayerbyusername(update.message.text.split(' ')[1])
            if target is not None:
                player.votingfor = target
                bot.sendMessage(update.message.chat['id'], "Hai votato per uccidere {0}.".format(target.tusername))
            else:
                bot.sendMessage(update.message.chat['id'], "Il nome utente specificato non esiste.")
        else:
            bot.sendMessage(update.message.chat['id'], "Non puoi votare. Non sei nella partita o sei morto.")
    else:
        bot.sendMessage(update.message.chat['id'], "Nessuna partita in corso trovata.")


def endday(bot, update):
    game = findgamebyid(update.message.chat['id'])
    if game is not None and game.phase is 'Voting' and update.message.from_user['id'] == game.adminid:
        game.endday(bot)


def power(bot, update):
    if update.message.chat['type'] == 'private':
        # Ho un'idea su come farlo meglio. Forse.
        cmd = update.message.text.split(' ', 2)
        game = findgamebyid(int(cmd[1]))
        if game is not None:
            player = game.findplayerbyid(update.message.from_user['id'])
            if player.alive:
                player.role.power(bot, game, player, cmd[2])
            else:
                bot.sendMessage(update.message.chat['id'], "Sei morto e non puoi usare poteri.")
        else:
            bot.sendMessage(update.message.chat['id'], "Partita non trovata.")
    else:
        bot.sendMessage(update.message.chat['id'], "Per usare /power, scrivimi in chat privata a @mifiabot!")

updater.dispatcher.addTelegramCommandHandler('ping', ping)
updater.dispatcher.addTelegramCommandHandler('newgame', newgame)
updater.dispatcher.addTelegramCommandHandler('join', join)
updater.dispatcher.addTelegramCommandHandler('debug', debug)
updater.dispatcher.addTelegramCommandHandler('endjoin', endjoin)
updater.dispatcher.addTelegramCommandHandler('vote', vote)
updater.dispatcher.addTelegramCommandHandler('endday', endday)
updater.dispatcher.addTelegramCommandHandler('power', power)
updater.dispatcher.addTelegramCommandHandler('status', status)
updater.start_polling()
updater.idle()
