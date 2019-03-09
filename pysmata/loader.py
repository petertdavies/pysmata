import json
import numpy as np
import re
import copy
import collections

import pysmata.model as model

# This only matters for units that create units as a start of turn effect
unit_pos = { "Gauss Fabricator": 0
           , "Oxide Mixer" : 0
           , "Frost Brooder" : 0
           , "Defense Grid" : 0
           }

def read_cost(c):
  if type(c) == int:
    arr = np.zeros(6, np.int)
    arr[0] = c
    return arr # The fact that this happens is hilarious
  m = re.match("[0-9]+", c)
  arr = np.zeros(6, np.int)
  if m:
    arr[0] = int(m.group(0))
    c = c[m.end():]
  for ch in c:
    if ch == 'G':
      arr[1] += 1
    elif ch == 'B':
      arr[2] += 1
    elif ch == 'C':
      arr[3] += 1
    elif ch == 'H':
      arr[4] += 1
    elif ch == 'A':
      arr[5] += 1
    else:
      raise Exception("Bad char: " + ch)
  return arr

class Effect():
  def __init__(self, res=read_cost(""), sac=[], create=[], delete=False, hp_change = 0, freeze=None, exhaust=0, resonate=None, special=None):
    self.res = res
    self.sac = sac
    self.create = create
    self.delete = delete
    self.hp_change = hp_change
    self.freeze = freeze
    self.exhaust = exhaust
    self.resonate = resonate
    self.special = special

class Revert():
  def __init__(self, res, sac, create, delete, hp_change, clicked, exhaust):
    self.res = res
    self.sac = sac
    self.create = create
    self.delete = delete
    self.hp_change = hp_change
    self.clicked = clicked
    self.freeze = None
    self.exhaust = exhaust
    self.spent = False
    self.apollo = None

class Create():
  def __init__(self, data):
    self.unit_name = data[0]
    if data[1] == "own":
      self.opponent = False
    else:
      self.opponent = True
    
    if len(data) > 2:
      self.number = data[2]
    else:
      self.number = 1
    
    if len(data) > 3:
      self.buildtime = data[3]
    else:
      self.buildtime = 1
    
    if len(data) > 4:
      self.lifespan = data[4]
    else:
      self.lifespan = None

class Card():
  def __init__(self, data):
    self.data = data
    self.name = data['name']
    if 'toughness' in data:
      self.toughness = data['toughness']
    else:
      self.toughness = 1
    if "HPMax" in data:
      self.max_hp = data["HPMax"]
    else:
      self.max_hp = self.toughness
    self.blocker = bool(data['defaultBlocking'])
    if 'buildTime' in data:
      self.buildtime = data['buildTime']
    else:
      self.buildtime = 1
    
    if "lifespan" in data:
      self.lifespan = int(data["lifespan"])
    else:
      self.lifespan = None
    
    self.fragile = bool(data.get("fragile", False))
    
    self.spell = bool(data.get("spell", False))
    
    self.stamina = data.get("charge", None)
    
    self.supply = { "trinket" : 20
                  , "normal" : 10
                  , "rare" : 4
                  , "legendary" : 1
                  , None : 0
                  } [data.get("rarity")]
    
    self.frontline = bool(data.get("undefendable", False))
    
    if "abilityScript" in data or "targetAction" in data:
      hp_change = -data.get("HPUsed", 0)
      
      if "abilityScript" in data and "receive" in data["abilityScript"]:
        abilityReceive = read_cost(data["abilityScript"]["receive"])
      else:
        abilityReceive = read_cost("")
      
      if "abilityCost" in data:
        abilityCost = read_cost(data["abilityCost"])
      else:
        abilityCost = read_cost("")
      
      if "abilitySac" in data:
        abilitySac = []
        for sac_detail in data["abilitySac"]:
          if len(sac_detail) == 1:
            abilitySac.append(sac_detail[0])
          else:
            abilitySac += [sac_detail[0]] * sac_detail[1]
      else:
        abilitySac = []
      
      if "abilityScript" in data and "create" in data["abilityScript"]:
        abilityCreate = [Create(d) for d in data["abilityScript"]["create"]]
      else:
        abilityCreate = []
      
      if "abilityScript" in data:
        selfsac = data["abilityScript"].get("selfsac", False)
      else:
        selfsac = False
      
      if "targetAction" in data and data["targetAction"] == "disrupt":
        freeze = data["targetAmount"]
      else:
        freeze = None
      
      if "targetAction" in data and data["targetAction"] == "snipe":
        special = self.name.lower().replace(" ", "")
        if special == "arsonist":
          special = "kineticdriver"
        elif special == "flameassassin":
          special = "apollo"
      elif "abilityNetherfy" in data and data["abilityNetherfy"] == True:
        special = "deadeye"
      else:
        special = None
      
      if "abilityScript" in data and "delay" in data["abilityScript"]:
        exhaust = data["abilityScript"]["delay"]
      else:
        exhaust = None
      self.click = Effect(abilityReceive - abilityCost, sac = abilitySac, create = abilityCreate, delete = selfsac, hp_change = hp_change, freeze = freeze, exhaust = exhaust, special = special)
    else:
      self.click = None
    
    hp_gained = data.get("HPGained", 0)
    
    if "beginOwnTurnScript" in data:
      create = [Create(d) for d in data["beginOwnTurnScript"].get("create", [])]
      selfsac = data["beginOwnTurnScript"].get("selfsac", False)
      exhaust = data["beginOwnTurnScript"].get("delay", 0)
      if "goldResonate" in data:
        special = "savior"
      else:
        special = None
      self.start_turn = Effect(read_cost(data["beginOwnTurnScript"].get("receive", "")), create = create, delete = selfsac, hp_change = hp_gained, exhaust = exhaust, resonate = data.get("resonate"), special = special)
    else:
      self.start_turn = Effect(hp_change = hp_gained, resonate=data.get("resonate"))
    
    if "buyScript" in data and "create" in data["buyScript"]:
      buyCreate = [Create(d) for d in data["buyScript"]["create"]]
    else:
      buyCreate = []
    
    if "buySac" in data:
      sac = []
      for sac_detail in data["buySac"]:
        if len(sac_detail) == 1:
          sac.append(sac_detail[0])
        else:
          sac += [sac_detail[0]] * sac_detail[1]
      self.buy = Effect(-read_cost(data.get('buyCost', "")), sac = sac, create = buyCreate)
    else:
      self.buy = Effect(-read_cost(data.get('buyCost', "")), create = buyCreate)

class UndoClick():
  def __init__(self, _id):
    self._id = _id
  def undo(self, state):
    state.unclick(self._id)
  def __str__(self):
    return "Undo Click " + str(self._id)

class UndoComposite():
  def __init__(self, undos):
    self.undos = undos
  def undo(self, state):
    for undo in reversed(self.undos):
      undo.undo(state)
  def amend(self, undo):
    self.undos.append(undo)
  def __str__(self):
    return "UndoComposite [" + ','.join(str(u) for u in self.undos) + "]"

class UndoPurchase():
  def __init__(self, _id):
    self._id = _id
  def undo(self, state):
    state.unbuild(self._id)
  def __str__(self):
    return "Undo Purchase " + str(self._id)

class UndoStartBreach():
  def undo(self, state):
    for _id in state.died_breach:
      state.units[_id].dead = False
    state.res[5] += state.breach_amt
    state.breach_amt = 0
    state.died_breach = set()
    state.breaching = False
  def __str__(self):
    return "Undo Start Breach"

class UndoEndBreach():
  def __init__(self, died_breach):
    self.died_breach = died_breach
  def undo(self, state):
    for _id in self.died_breach:
      state.units[_id].dead = True
      state.breach_amt += state.units[_id].health
      state.res[5] += state.units[_id].health
    state.died_breach = self.died_breach
    state.breaching = True
  def __str__(self):
    return "Undo End Breach"

class UndoNil():
  def undo(self, state):
    pass
  def __str__(self):
    return "UndoNil"

class UndoUnclick():
  def __init__(self, _id, r):
    self._id = _id
    self.r = r
  def undo(self, state):
    state.undoRevert(self.r)
  def __str__(self):
    return "Undo Unclick " + str(self._id)

class UndoUnpurchase():
  def __init__(self, _id, r):
    self._id = _id
    self.r = r
  def undo(self, state):
    state.undoRevert(self.r)
    if state.units[self._id].bought:
      state.bought[state.units[self._id].card.name] += 1
      state.supplies[state.units[self._id].card.name] -= 1
    state.units[self._id].dead = False
  def __str__(self):
    return "Undo Unpurchase " + str(self._id)

class UndoUnfreeze():
  def __init__(self, _id, freeze_sources):
    self._id = _id
    self.freeze_sources = freeze_sources
  def undo(self, state):
    for source_id in self.freeze_sources:
      state.click_unit(source_id)
      state.applyFreeze(self._id)
  def __str__(self):
    return "Undo Unfreeze " + str(self._id)

class UndoDefend():
  def __init__(self, _id):
    self._id = _id
  def undo(self, state):
    state.undefend(self._id)
  def __str__(self):
    return "Undo Defend " + str(self._id)

class UndoUndefend():
  def __init__(self, _id):
    self._id = _id
  def undo(self, state):
    state.defend(self._id)
  def __str__(self):
    return "Undo Undefend " + str(self._id)

class UndoFrontline():
  def __init__(self, _id):
    self._id = _id
  def undo(self, state):
    state.unfrontline(self._id)
  def __str__(self):
    return "Undo Frontline " + str(self._id)

class UndoUnfrontline():
  def __init__(self, _id, r):
    self._id = _id
    self.r = r
  def undo(self, state):
    state.undoRevert(self.r)
    state.died_frontline.add(self._id)
  def __str__(self):
    return "Undo Unfrontline " + str(self._id)

class UndoBreachKill():
  def __init__(self, _id):
    self._id = _id
  def undo(self, state):
    state.unbreach_kill(self._id)
  def __str__(self):
    return "Undo Breach Kill " + str(self._id)

class UndoUnbreach():
  def __init__(self, _id, r=None):
    self._id = _id
    self.r = r
  def undo(self, state):
    state.breach_kill(self._id)
    if self.r != None:
      state.undoRevert(self.r)

class UndoAdvance():
  def __init__(self, prev):
    self.prev = prev
  def undo(self, state):
    state.state = self.prev
  def str(self):
    return "Undo Advance"

class UndoDefendComplete():
  def undo(self, state):
    state.state = "defend"
    state.unstart_turn()
  def __str__(self):
    return "Undo Defend Complete"

class UndoRevert():
  def __init__(self, state):
    self.state = state
  def undo(self, state):
    return self.state
  def __str__(self):
    return "Undo Revert"

class Unit():
  def __init__(self, card, side, buildtime = None):
    self.card = card
    self.side = side
    if buildtime == None:
      buildtime = card.buildtime
    self.buildtime = buildtime
    self.dead = False
    self.clicked = False
    self.built_this_turn = True
    self.lifespan = card.lifespan
    self.freeze = 0
    self.freeze_sources = set()
    self.health = card.toughness
    self.exhaust = 0
    self.stamina = card.stamina
    self.reverts = []
    
    self.unstart = set()
  
  def start_turn(self):
    self.unstart = set()
    self.built_this_turn = False
    self.start_turn_health = self.health
    if self.card.spell:
      self.dead = True
      return Effect()
    if self.buildtime > 0:
      self.buildtime -= 1
      self.unstart.add("buildtime")
      if self.buildtime > 0:
        return Effect()
    if self.exhaust > 0:
      self.exhaust -= 1
      self.unstart.add("exhaust")
      if self.exhaust > 0:
        return Effect()
    if self.lifespan != None and not ("buildtime" in self.unstart or "exhaust" in self.unstart):
      self.unstart.add("lifespan")
      self.lifespan -= 1
      if self.lifespan == 0:
        self.dead = True
        return Effect()
    if self.clicked or self.freeze >= self.health:
      # The only reason we care about freeze now is blocking status so this works
      self.unstart.add("was_clicked")
      self.clicked = False
    self.freeze = 0
    self.freeze_sources = set()
    return self.card.start_turn
  
  def unstart_turn(self):
    # Undo enough of what start_turn did, so it can be called again
    # Reverting the start_turn effect is dealt with separately
    if "buildtime" in self.unstart:
      self.buildtime += 1
    if "lifespan" in self.unstart:
      self.lifespan += 1
    if "exhaust" in self.unstart:
      self.exhaust += 1
    if "was_clicked" in self.unstart:
      self.clicked = True
    if self.dead:
      self.dead = False
  
  def is_blocking(self):
    return self.card.blocker and not self.clicked and self.buildtime == 0 and self.exhaust == 0 and self.freeze < self.health

class State():
  def __init__(self, cards, assembler, units1, units2, supsup, infinitesupplies):
    self.assembler = assembler
    self.cards = cards
    self.card_by_name = {}
    for _id, card in enumerate(cards):
      self.card_by_name[card.name] = _id
    self.state = "buy"
    self.p1res = read_cost("")
    self.p2res = read_cost("")
    self.player = 1
    self.freezing = []
    self.died_defending = set()
    self.final_defender = None
    self.died_breach = set()
    self.final_breach = None
    self.turn = 0
    self.clicked = set()
    self.ply = 0
    self.apolloing = []
    self.apolloed = {}
    
    self.undos = []
    self.current_swipe_undos = []
    
    self.units = []
    for n, name in units1:
      for _ in range(n):
        self.units.append(Unit(self.cards[self.card_by_name[name]], side = 1))
    for n, name in units2:
      for _ in range(n):
        self.units.append(Unit(self.cards[self.card_by_name[name]], side = 2))
    
    if infinitesupplies:
      self.p1supplies = { card.name : 2**16-1 for card in self.cards }
      self.p2supplies = { card.name : 2**16-1 for card in self.cards }
    else:
      self.p1supplies = { card.name : card.supply for card in self.cards }
      self.p2supplies = { card.name : card.supply for card in self.cards }
    
    for supinfo in supsup[0]:
      if len(supinfo) == 2:
        self.p1supplies[supinfo[0]] = supinfo[1]
    for supinfo in supsup[1]:
      if len(supinfo) == 2:
        self.p2supplies[supinfo[0]] = supinfo[1]
     
    
    #did = self.card_by_name["Drone"]
    #eid = self.card_by_name["Engineer"]
    #self.units = [Unit(cards[did], side = 1),Unit(cards[did], side = 1),Unit(cards[did], side = 1),Unit(cards[did], side = 1),Unit(cards[did], side = 1),Unit(cards[did], side = 1),Unit(cards[eid], side = 1),Unit(cards[eid], side = 1),Unit(cards[did], side = 2),Unit(cards[did], side = 2),Unit(cards[did], side = 2),Unit(cards[did], side = 2),Unit(cards[did], side = 2),Unit(cards[did], side = 2),Unit(cards[did], side = 2),Unit(cards[eid], side = 2),Unit(cards[eid], side = 2)]
    
    self.assembler.record_gamestate(self)
    self.start_turn()
  
  def log(self, s):
    self.assembler.log_plain(s)
  
  def print_log(self, *args):
    if self.assembler.log_file != None:
      print(*args, file=self.assembler.log_file)
  
  @property
  def res(self):
    if self.player == 1:
      return self.p1res
    else:
      return self.p2res
  
  @res.setter
  def res(self, x):
    if self.player == 1:
      self.p1res = x
    else:
      self.p2res = x
  
  @property
  def oppres(self):
    if self.player == 1:
      return self.p2res
    else:
      return self.p1res
  
  @oppres.setter
  def oppres(self, x):
    if self.player == 1:
      self.p2res = x
    else:
      self.p1res = x
  
  @property
  def opponent(self):
    if self.player == 1:
      return 2
    else:
      return 1
  
  @property
  def supplies(self):
    if self.player == 1:
      return self.p1supplies
    else:
      return self.p2supplies
      self.p1res = x
  
  def player_units(self, name, include_dead=False, reverse=True):
    if not reverse:
      yield from sorted((up for up in enumerate(self.units) if (up[1].dead == False or include_dead) and up[1].side == self.player and (up[1].card.name == name or name == None)), key = lambda up: (-up[1].health, -up[1].stamina if up[1].stamina != None else -1000, up[1].lifespan if up[1].lifespan != None else 1000))
    else:
      yield from sorted((up for up in reversed(list(enumerate(self.units))) if (up[1].dead == False or include_dead) and up[1].side == self.player and (up[1].card.name == name or name == None)), key = lambda up: (-up[1].health, -up[1].stamina if up[1].stamina != None else -1000, up[1].lifespan if up[1].lifespan != None else 1000))

  def opp_units(self, name, include_dead=False, reverse=False):
    if reverse:
      yield from sorted((up for up in reversed(list(enumerate(self.units))) if (up[1].dead == False or include_dead) and up[1].side != self.player and (up[1].card.name == name or name == None)), key = lambda up: (up[1].health, up[1].stamina if up[1].stamina != None else 1000, up[1].lifespan if up[1].lifespan != None else 1000))
    else:
      yield from sorted((up for up in enumerate(self.units) if (up[1].dead == False or include_dead) and up[1].side != self.player and (up[1].card.name == name or name == None)), key = lambda up: (up[1].health, up[1].stamina if up[1].stamina != None else 1000, up[1].lifespan if up[1].lifespan != None else 1000))
  
  def canApplyEffect(self, e, _id):
    if not (self.res >= -e.res).all():
      return False
    rsac = []
    for unit_name in e.sac:
      for unit_id, unit in self.player_units(unit_name):
        if unit.buildtime == 0 and unit.exhaust == 0 and unit_id not in rsac:
          rsac.append(unit_id)
          break
    if len(rsac) < len(e.sac):
      return False
    if self.units[_id].health < -e.hp_change:
      return False
    if e.special == "deadeye":
      can_deadeye = False
      for unit_id, unit in self.opp_units("Drone"):
        self.print_log(unit_id)
        if unit.buildtime == 0 and not unit.is_blocking():
          self.print_log(unit_id)
          can_deadeye = True
      if not can_deadeye:
        return False
    return True
  
  def applyEffect(self, e, _id, purchasing=False):
    units_subclicked = []
    if not self.canApplyEffect(e, _id):
      raise Exception("Effect not applyable")
    self.res += e.res
    if self.res[5] > 0 and self.final_breach != None:
      self.unbreach_kill(None)
    rres = np.copy(e.res)
    rcreate = []
    for create in e.create:
      rcreate += (self.applyCreate(create, _id, purchasing))
    rsac = []
    for unit_name in e.sac:
      sacced = False
      unclicked_alt = None
      for unit_id, unit in self.player_units(unit_name):
        if unit.exhaust == 0 and unit.buildtime == 0:
          if not unit.clicked and unit.card.click != None:
            if unclicked_alt == None:
              unclicked_alt = unit_id
          else:
            unit.dead = True
            rsac.append(unit_id)
            self.sacced_this_turn.add(unit_id)
            sacced = True
            break
      if not sacced:
        if unclicked_alt != None:
          self.click_unit(unclicked_alt)
          units_subclicked.append(unclicked_alt)
          self.units[unclicked_alt].dead = True
          rsac.append(unclicked_alt)
          self.sacced_this_turn.add(unclicked_alt)
        else:
          raise Exception("Could not Sac " + unit_name)
    if e.delete:
      self.units[_id].dead = True
      rdelete = _id
    else:
      rdelete = None
    
    r_hp_change = e.hp_change
    if e.hp_change != 0:
      assert self.units[_id].card.fragile
      assert self.units[_id].health >= -e.hp_change
      self.units[_id].health += e.hp_change
      if self.units[_id].health == 0:
        self.units[_id].dead = True
      elif self.units[_id].health > self.units[_id].card.max_hp:
        dif = self.units[_id].health - self.units[_id].card.max_hp
        r_hp_change = e.hp_change - dif
        self.units[_id].health = self.units[_id].card.max_hp
    self.units[_id].actual_hp_change = r_hp_change
    
    if e.exhaust:
      self.units[_id].exhaust += e.exhaust
    
    if e.resonate != None:
      self.res[5] += self.resonate_num[e.resonate]
      rres[5] += self.resonate_num[e.resonate]
    
    if e.special == "deadeye":
      exhaust_alt = None
      for unit_id, unit in reversed(list(self.opp_units("Drone"))):
        sacced = False
        if unit.buildtime == 0 and not unit.is_blocking():
          # Yes, If you freeze a Drone you can then snipe it with Deadeye
          if unit.exhaust != 0:
            if exhaust_alt == None:
              exhaust_alt = unit_id
          else:
            unit.dead = True
            rsac.append(unit_id)
            self.sacced_this_turn.add(unit_id)
            sacced = True
            break
      if not sacced:
        if exhaust_alt != None:
          self.units[exhaust_alt].dead = True
          rsac.append(exhaust_alt)
          self.sacced_this_turn.add(exhaust_alt)
        else:
          raise Exception("Could not Deadeye")
    elif e.special == "savior":
      self.res[0] += self.resonate_num["Drone"]
      rres[0] += self.resonate_num["Drone"]
    
    r = Revert(rres, rsac, rcreate, rdelete, r_hp_change, _id, e.exhaust)
    self.units[_id].reverts.append(r)
    #for unit_id in rcreate:
    #  self.units[unit_id].revert = r
    
    return units_subclicked
  
  def applyRevert(self, r):
    assert not r.spent
    r.spent = True
    self.res -= r.res
    assert (self.res >= 0).all()
    r.resurrected = []
    for _id in r.sac:
      name = self.units[_id].card.name
      for (unit_id, unit) in enumerate(self.units):
        if unit.side == self.units[_id].side and unit.dead and unit.card.name == name and unit_id in self.sacced_this_turn:
          self.units[unit_id].dead = False
          self.sacced_this_turn.remove(unit_id)
          r.resurrected.append(unit_id)
          break
    for _id in r.create:
      self.units[_id].dead = True
    if r.delete:
      self.units[r.delete].dead = False
    
    if r.clicked in self.clicked:
      self.units[r.clicked].clicked = False
      self.clicked.remove(r.clicked)
      r.actually_undo_reversion_of_clicking = True # For undoRevert()
    else:
      r.actually_undo_reversion_of_clicking = False
    
    if r.freeze != None:
      (target_id, amt) = r.freeze
      self.units[target_id].freeze -= amt
      self.units[target_id].freeze_sources.remove(r.clicked)
      self.breaching = False
    
    if self.units[r.clicked].health == 0:
      self.units[r.clicked].dead = False
    self.units[r.clicked].health -= r.hp_change
    
    if r.exhaust:
      self.units[r.clicked].exhaust -= r.exhaust
    
    if r.apollo != None:
      self.units[r.apollo].dead = False
      del self.apolloed[r.apollo]
    
    if r.clicked != None:
      assert self.units[r.clicked].reverts.pop() == r
      
  
  def undoRevert(self, r):
    assert r.spent
    r.spent = False
    self.res += r.res
    for _id in r.resurrected:
      self.sacced_this_turn.add(_id)
      self.units[_id].dead = True
    for _id in r.create:
      self.units[_id].dead = False
    if r.delete:
      self.units[r.delete].dead = True
    
    if r.actually_undo_reversion_of_clicking:
      self.units[r.clicked].clicked = True
      if self.units[r.clicked].stamina != None:
        self.units[r.clicked].stamina -= 1
      self.clicked.add(r.clicked)
    del r.actually_undo_reversion_of_clicking
    
    if r.freeze != None:
      (target_id, amt) = r.freeze
      self.units[target_id].freeze += amt
      self.units[target_id].freeze_sources.add(r.clicked)
    
    self.units[r.clicked].health += r.hp_change
    if self.units[r.clicked].health == 0:
      self.units[r.clicked].dead = True
        
    if r.exhaust:
      self.units[r.clicked].exhaust += r.exhaust
    
    if r.apollo != None:
      self.units[r.apollo].dead = True
      self.apolloed[r.apollo] = r.clicked
    
    if r.clicked != None:
      self.units[r.clicked].reverts.append(r)
  
  def applyCreate(self, create, master, purchasing):
    _ids = []
    for i in range(create.number):
      if create.opponent and self.player == 1:
        side = 2
      elif create.opponent and self.player == 2:
        side = 1
      else:
        side = self.player
        
      self.print_log(create.unit_name, len(self.units))
      self.units.append(Unit(self.cards[self.card_by_name[create.unit_name]], side = side))
      self.units[-1].bought = False
      if purchasing:
        self.units[-1].buildtime = create.buildtime
      else:
        self.units[-1].exhaust = create.buildtime
        self.units[-1].buildtime = 0
      if create.lifespan != None:
        self.units[-1].lifespan = create.lifespan
      self.units[-1].master = master
      
      _ids.append(len(self.units)-1)
    return _ids
  
  def applyFreeze(self, _id):
    while self.freezing != [] and self.units[_id].freeze < self.units[_id].health:
      (source_id, amt) = self.freezing.pop(0)
      self.undos[-1].amend(self.click_unit(source_id))
      self.units[_id].freeze += amt
      self.units[_id].freeze_sources.add(source_id)
      self.units[source_id].reverts[-1].freeze = (_id, amt)
  
  def shiftApplyFreeze(self, _id):
    name = self.units[_id].card.name
    first_time = True
    for unit_id, unit in sorted(self.opp_units(name, reverse = False), key=lambda up: -up[1].health):
      if unit.is_blocking() and (sum((amt for (_, amt) in self.freezing)) >= unit.health or first_time):
        first_time = False
        self.applyFreeze(unit_id)
        if self.freezing == []:
          break
  
  def freeze_click(self, _id):
    self.freezing.append((_id, self.units[_id].card.click.freeze))
    return UndoComposite([])
  
  def shift_freeze_click(self, _id):
    name = self.units[_id].card.name
    for unit_id, unit in self.player_units(name, reverse=False):
      if not unit.clicked and unit.buildtime == 0 and not unit.built_this_turn and unit.stamina != 0:
        self.freeze_click(unit_id)
    return UndoComposite([])
  
  def apollo_click(self, _id):
    self.apolloing.append(_id)
    return UndoComposite([])
  
  def shift_apollo_click(self, _id):
    name = self.units[_id].card.name
    for unit_id, unit in self.player_units(name, reverse=False):
      self.apollo_click(unit_id)
    return UndoComposite([])
  
  def buy(self, _id):
    self.bought[self.cards[_id].name] += 1
    self.supplies[self.cards[_id].name] -= 1
    self.units.append(Unit(self.cards[_id], side = self.player))
    unit_id = len(self.units) - 1
    self.units[-1].bought = True
    self.units[-1].master = None
    subclicked = self.applyEffect(self.cards[_id].buy, len(self.units)-1, purchasing=True)
    return UndoComposite([UndoClick(unit_id) for unit_id in subclicked] + [UndoPurchase(unit_id)])
  
  def shift_buy(self, _id):
    undos = []
    n = 0
    while self.supplies[self.cards[_id].name] > 0 and self.canApplyEffect(self.cards[_id].buy, len(self.units)-1):
      undos.append(self.buy(_id))
      n += 1
    self.print_log("Shift Purchased", self.cards[_id].name, n)
    return UndoComposite(undos)
  
  def create(self, _id):
    self.print_log(len(self.units))
    self.units.append(Unit(self.cards[_id], side = self.player))
    self.units[-1].exhaust = self.units[-1].buildtime
    self.units[-1].buildtime = 0
    self.units[-1].bought = False
    self.units[-1].master = None
  
  def start_turn(self):
    self.clicked = set()
    self.bought = collections.defaultdict(int)
    self.died_breach = set()
    self.final_breach = None
    self.breaching = False
    self.breach_amt = 0
    self.died_frontline = set()
    self.started_turn = []
    self.start_turn_unit_counter = len(self.units)
    self.sacced_this_turn = set()
    if self.player == 1:
      self.p1res[2] = 0
      self.p1res[3] = 0
      self.p1res[4] = 0
      self.p1res[5] = 0
      self.turn += 1
    else:
      self.p2res[2] = 0
      self.p2res[3] = 0
      self.p2res[4] = 0
      self.p2res[5] = 0
    self.resonate_num = {}
    for name in ["Drone", "Tarsier", "Tesla Tower", "Engineer", "Sentinel", "Forcefield", "Blood Barrier"]:
      num = 0
      for unit_id, unit in self.player_units(name):
        if unit.buildtime + unit.exhaust <= 1:
          num += 1
      self.resonate_num[name] = num
    
    unit_list = sorted(list(enumerate(self.units.copy())), key=lambda x: unit_pos.get(x[1].card.name, 0))
    for _id, unit in unit_list:
      if unit.side == self.player and unit.dead == False:
        self.applyEffect(unit.start_turn(), _id)
        unit.start_turn_revert = unit.reverts[-1]
        self.started_turn.append(_id)
  
  def unstart_turn(self):
    for _id in reversed(self.started_turn):
      self.applyRevert(self.units[_id].start_turn_revert)
      self.units[_id].unstart_turn()
    self.units = self.units[:self.start_turn_unit_counter] #WUT
    if self.player == 1:
      self.turn -= 1
  
  def click_unit(self, _id):
    self.units[_id].pre_click_health = self.units[_id].health
    self.clicked.add(_id)
    subclicked = self.applyEffect(self.units[_id].card.click, _id)
    self.units[_id].clicked = True
    if self.units[_id].stamina != None:
      assert self.units[_id].stamina != 0
      self.units[_id].stamina -= 1
    return UndoComposite([UndoClick(__id) for __id in subclicked + [_id]])
  
  def shift_click_unit(self, _id):
    name = self.units[_id].card.name
    undos = []
    for unit_id, unit in sorted((up for up in enumerate(self.units) if up[1].dead == False and up[1].side == self.player and up[1].card.name == name), key = lambda up: (up[1].health if up[1].is_blocking() else -up[1].health, -up[1].stamina if up[1].stamina != None else -1000, up[1].lifespan if up[1].lifespan != None else 1000)):
      if not unit.clicked and unit.buildtime == 0 and unit.exhaust == 0 and not unit.built_this_turn and unit.stamina != 0 and unit.card.name == name and unit.dead == False and unit.side == self.player:
        if self.canApplyEffect(self.units[_id].card.click, unit_id):
          undos.append(self.click_unit(unit_id))
    return UndoComposite(undos)

  def unclick(self, _id):
    r = self.units[_id].reverts[-1]
    self.applyRevert(r)
    if self.units[_id].stamina != None:
      self.units[_id].stamina += 1
    return UndoUnclick(_id, r)
  
  def shift_unclick_unit(self, _id):
    name = self.units[_id].card.name
    undos = []
    for unit_id, unit in reversed(list(self.player_units(name, include_dead=True))):
      if unit_id in self.clicked and (self.res >= unit.reverts[-1].res).all() and not unit_id in self.sacced_this_turn:
        undos.append(self.unclick(unit_id))
    return UndoComposite(undos)
  
  def unbuild(self, _id):
    subUndos = []
    if self.units[_id].master != None:
      # Unit was constructed by something else, so undo that instead
      if self.units[self.units[_id].master].built_this_turn:
        return self.unbuild(self.units[_id].master)
      else:
        return self.unclick(self.units[_id].master)
    else:
      r = self.units[_id].reverts[-1]
      self.applyRevert(r)
      if self.units[_id].bought:
        self.bought[self.units[_id].card.name] -= 1
        self.supplies[self.units[_id].card.name] += 1
      self.units[_id].dead = True
      return UndoUnpurchase(_id, r)
  
  def shift_unbuild(self, _id):
    if self.units[_id].master != None:
      # Unit was constructed by something else, so undo that instead
      if self.units[self.units[_id].master].built_this_turn:
        return self.shift_unbuild(self.units[_id].master)
      else:
        return self.shift_unclick_unit(self.units[_id].master)
    name = self.units[_id].card.name
    undos = []
    for _id, unit in self.player_units(name):
      if unit.built_this_turn and unit.master == None:
        undos.append(self.unbuild(_id))
    return UndoComposite(undos)
    
  
  def unfreeze(self, _id):
    fs_copy = self.units[_id].freeze_sources.copy()
    for unit_id in fs_copy:
      self.applyRevert(self.units[unit_id].reverts[-1])
    return UndoUnfreeze(_id, fs_copy)
  
  def defend(self, _id):
    if self.units[_id].health <= self.oppres[5]:
      self.units[_id].dead = True
      self.oppres[5] -= self.units[_id].health
      self.died_defending.add(_id)
    else:
      self.absorb_amt = self.oppres[5]
      self.oppres[5] = 0
      self.final_defender = _id
      if self.units[_id].card.fragile:
        self.units[_id].health -= self.absorb_amt
    return UndoDefend(_id)
  
  def shift_unfreeze(self, _id):
    undos = []
    name = self.units[_id].card.name
    blocking = self.units[_id].is_blocking()
    for unit_id, unit in reversed(list(self.opp_units(name))):
      if unit.freeze > 0 and unit.is_blocking() == blocking:
        undos.append(self.unfreeze(unit_id))
    return UndoComposite(undos)
  
  def shift_defend(self, _id):
    undos = []
    name = self.units[_id].card.name
    for unit_id, unit in sorted((up for up in enumerate(self.units) if up[1].dead == False and up[1].side == self.player and (up[1].card.name == name or name == None)), key = lambda up: (-up[1].health, up[1].stamina if up[1].stamina != None else 1000, up[1].lifespan if up[1].lifespan != None else 1000)):
      if unit.is_blocking():
        undos.append(self.defend(unit_id))
        if self.oppres[5] == 0:
          break
    return UndoComposite(undos)
  
  def undefend(self, _id):
    if self.final_defender != None:
      if self.units[self.final_defender].card.fragile:
        self.units[self.final_defender].health += self.absorb_amt
      undo = UndoUndefend(self.final_defender)
      self.final_defender = None
      self.oppres[5] += self.absorb_amt
      del self.absorb_amt
      return undo
    else:
      self.oppres[5] += self.units[_id].health
      self.units[_id].dead = False
      self.died_defending.remove(_id) #DO THIS
      return UndoUndefend(_id)
  
  def shift_undefend(self, _id):
    undos = []
    name = self.units[_id].card.name
    if self.final_defender != None:
      if self.units[self.final_defender].card.name != name:
        return self.undefend(None)
      else:
        undos.append(self.undefend(None))
    for unit_id, unit in self.player_units(name, reverse=False, include_dead=True):
      if unit_id in self.died_defending:
        undos.append(self.undefend(unit_id))
    return UndoComposite(undos)
  
  def abandon_freeze(self):
    self.freezing = []
  
  def revert_all(self):
    state_copy = copy.deepcopy(self)
    self.print_log([str(u) for u in self.undos])
    while len(self.undos) != 0 and type(self.undos[-1]) != UndoDefendComplete:
      ret = self.undos.pop().undo(self)
      if ret != None:
        self = ret # LOOK AT ME
    
    if len(self.undos) != 0:
      self.undos.pop().undo(self)
    else:
      self.unstart_turn()
      self.start_turn()
    
    self.undos.append(UndoRevert(state_copy))
    return self
  
  def revert_defence(self):
    state_copy = copy.deepcopy(self)
    while len(self.undos) != 0:
      ret = self.undos.pop().undo(self)
      if ret != None:
        self = ret # LOOK AT ME
    self.undos.append(UndoRevert(state_copy))
    return self
    
  
  def do_breach(self, _id, shift=False):
    self.breaching = True
    self.breach_amt = 0
    for unit_id, unit in self.opp_units(None):
      if unit.card.blocker and not unit.clicked and unit.freeze < unit.health and unit.buildtime == 0 and unit.exhaust == 0:
        unit.dead = True
        self.died_breach.add(unit_id)
        self.breach_amt += unit.health
    self.res[5] -= self.breach_amt
    if _id != None and not _id in self.died_breach:
      if shift:
        undos = [self.shift_breach_kill(_id)]
      else:
        undos = [self.breach_kill(_id)]
    else:
      undos = []
    assert self.res[5] >= 0
    return UndoComposite([UndoStartBreach()] + undos)
  
  def breach_kill(self, _id):
    if self.res[5] >= self.units[_id].health:
      self.died_breach.add(_id)
      self.breach_amt += self.units[_id].health
      self.res[5] -= self.units[_id].health
      self.units[_id].dead = True
    else:
      assert self.units[_id].card.fragile
      self.final_breach = _id
      self.final_breach_amt = self.res[5]
      self.breach_amt += self.res[5]
      self.units[_id].health -= self.res[5]
      self.res[5] = 0
    return UndoBreachKill(_id)
  
  def shift_breach_kill(self, _id):
    name = self.units[_id].card.name
    undos = []
    for unit_id, unit in self.opp_units(name, reverse=False):
      if (self.res[5] >= unit.health or (unit.card.fragile and self.res[5] > 0)) and unit.buildtime == 0:
        undos.append(self.breach_kill(unit_id))
    return UndoComposite(undos)
  
  def unbreach_kill(self, _id):
    if self.final_breach != None:
      r = None
      if self.final_breach in self.apolloed:
        r = self.units[self.apolloer].reverts[-1]
        self.applyRevert(r)
      self.units[self.final_breach].health += self.final_breach_amt
      final_breach = self.final_breach
      self.final_breach = None
      self.breach_amt -= self.final_breach_amt
      self.res[5] += self.final_breach_amt
      del self.final_breach_amt
      return UndoUnbreach(final_breach, r)
    else:
      self.units[_id].dead = False
      self.breach_amt -= self.units[_id].health
      self.died_breach.remove(_id)
      self.res[5] += self.units[_id].health
      return UndoUnbreach(_id)
  
  def shift_unbreach_kill(self, _id):
    undos = []
    if self.final_breach != None:
      if self.units[self.final_breach].card.name == self.units[_id].card.name:
        undos.append(self.unbreach_kill(None))
      else:
        return self.unbreach_kill(None)
    for unit_id, unit in self.opp_units(self.units[_id].card.name, include_dead=True):
      if unit_id in self.died_breach:
        self.unbreach_kill(unit_id)
    return UndoComposite(undos)
  
  def end_breach(self):
    db_copy = self.died_breach.copy()
    for _id in db_copy:
      self.units[_id].dead = False
      self.breach_amt -= self.units[_id].health
      self.res[5] += self.units[_id].health
    assert self.breach_amt == 0
    self.died_breach = set()
    self.breaching = False
    return UndoEndBreach(db_copy)
  
  def apolloSnipe(self, _id):
    apollo_id = self.apolloing.pop(0)
    self.units[_id].dead = True
    self.undos[-1].amend(self.click_unit(apollo_id))
    self.units[_id].reverts.append(self.units[apollo_id].reverts[-1])
    self.units[apollo_id].reverts[-1].apollo = _id
    self.apolloed[_id] = apollo_id
    self.apolloer = apollo_id
  
  def shiftApolloSnipe(self, _id):
    name = self.units[_id].card.name
    blocking = self.units[_id].is_blocking()
    for unit_id, unit in sorted(self.opp_units(name, reverse = False), key=lambda up: -up[1].health):
      if self.apolloing == []:
        return
      elif unit.is_blocking() == blocking:
        self.apolloSnipe(unit_id)
  
  def abandon_snipe(self):
    self.apolloing = []
  
  def frontline_snipe(self, _id):
    health = self.units[_id].health
    self.applyEffect(Effect(res=np.array([0,0,0,0,0,-health]), delete=True), _id)
    self.died_frontline.add(_id)
    return UndoFrontline(_id)
  
  def unfrontline(self, _id):
    r = self.units[_id].reverts[-1]
    self.applyRevert(r)
    self.died_frontline.remove(_id)
    return UndoUnfrontline(_id, r)
  
  def shift_frontline_snipe(self, _id):
    name = self.units[_id].card.name
    health = self.units[_id].health
    blocking = self.units[_id].is_blocking()
    undos = []
    for _id, unit in self.opp_units(name, reverse=False):
      if self.res[5] < health:
        break
      elif unit.buildtime == 0 and unit.is_blocking() == blocking:
        undos.append(self.frontline_snipe(_id))
    return UndoComposite(undos)
  
  def shift_unfrontline_snipe(self, _id):
    name = self.units[_id].card.name
    blocking = self.units[_id].is_blocking()
    undos = []
    for _id in self.died_frontline.copy():
      if self.units[_id].card.name == name and self.units[_id].is_blocking() == blocking:
        undos.append(self.unfrontline(_id))
    return UndoComposite(undos)
  
  def calc_opp_defence(self):
    defence = 0
    for _id, unit in enumerate(self.units):
      if not unit.dead and unit.side != self.player and unit.is_blocking():
        defence += unit.health
    return defence
  
  def print_units(self, side):
    tally = collections.defaultdict(int)
    for unit in self.units:
      if not unit.dead and unit.side == side:
        tally[unit.card.name] += 1
    for (name, num) in tally.items():
      self.print_log(name, num)
  
  def do_action(self, action):
    if action['_type'] == "undo clicked":
      self.print_log(self.undos[-1])
      return self.undos.pop().undo(self)
    elif action['_type'] == "space clicked":
      if self.state == "buy" and not self.breaching and self.res[5] > 0 and self.calc_opp_defence() <= self.res[5]:
        self.print_log("Start Breach SpaceBar")
        self.undos.append(self.do_breach(None))
      else:
        self.undos.append(self.advance_state())
    elif action['_type'].startswith("emote"):
      pass
    elif action['_type'] == "revert clicked":
      if self.state == "buy":
        self.print_log("Reverted")
        return self.revert_all()
      elif self.state == "defend":
        self.print_log("Reverted Defence")
        return self.revert_defence()
      elif self.state == "commit":
        self.print_log("Reverted End Turn")
        self.undos.pop().undo(self)
    elif self.freezing != []:
      if action['_type'] in ["inst clicked", "inst shift clicked"] and (self.units[action['_id']].side == self.player or self.units[action['_id']].is_blocking() == False):
        self.print_log("Freeze Terminated", self.freezing)
        self.freezing = []
        self.do_action(action)
      if action['_type'] == "inst clicked":
        self.print_log("Apply freeze", self.units[action['_id']].card.name, action["_id"])
        self.applyFreeze(action['_id'])
      elif action['_type'] == "inst shift clicked":
        self.print_log("Shift apply freeze", self.units[action['_id']].card.name)
        self.shiftApplyFreeze(action['_id'])
      elif action['_type'] == "cancel target processed":
        self.print_log("Abandon freeze")
        self.abandon_freeze()
      elif action['_type'] == "end swipe processed":
        self.print_log("End Swipe (nil)")
        #self.undos.append(UndoComposite(self.current_swipe_undos))
        assert self.current_swipe_undos == []
        self.current_swipe_undos = []
      elif action['_type'] == "card clicked":
        self.freezing = []
        self.do_action(action)
      else:
        raise Exception("Unimplemented action", action['_type'])
    elif self.apolloing != []:
      if action['_type'] == "inst clicked":
        self.print_log("Apollo Snipe", self.units[action['_id']].card.name, action['_id'])
        self.apolloSnipe(action['_id'])
      elif action['_type'] == "inst shift clicked":
        self.print_log("Shift Apollo Snipe", self.units[action['_id']].card.name, action['_id'])
        self.shiftApolloSnipe(action['_id'])
      elif action['_type'] == "cancel target processed":
        self.print_log("Abandon Snipe")
        self.abandon_snipe()
      elif action['_type'] == "card clicked":
        self.apolloing = []
        self.do_action(action)
      elif action['_type'] == "end swipe processed":
        self.print_log("End Swipe (nil)")
      else:
        raise Exception("Unimplemented action", action['_type'])
    elif self.state == "buy":
      if action['_type'] == "inst shift clicked":
        if self.units[action['_id']].side != self.player and not self.units[action['_id']].dead and self.units[action['_id']].card.frontline and self.units[action["_id"]].freeze == 0:
          self.print_log("Shift Frontline Snipe", self.units[action['_id']].card.name, action['_id'])
          self.undos.append(self.shift_frontline_snipe(action['_id']))
        elif self.final_breach == None and action['_id'] in self.died_frontline:
          self.print_log("Shift Unfrontline Snipe", self.units[action['_id']].card.name, action['_id'])
          self.undos.append(self.shift_unfrontline_snipe(action['_id']))
        elif self.breaching and self.final_breach == None and not self.units[action['_id']].dead and self.units[action['_id']].side != self.player:
          self.print_log("Shift Breach Kill", self.units[action['_id']].card.name, action['_id'])
          self.undos.append(self.shift_breach_kill(action['_id']))
        elif self.breaching and self.units[action['_id']].side != self.player and self.units[action['_id']].is_blocking():
          self.print_log("Shift End Breach", self.units[action['_id']].card.name, action['_id'])
          self.undos.append(self.end_breach())
        elif self.breaching and self.units[action['_id']].side != self.player:
          self.print_log("Shift Unbreach Kill", self.units[action['_id']].card.name, action['_id'])
          self.undos.append(self.shift_unbreach_kill(action['_id']))
        elif self.units[action['_id']].freeze > 0:
          self.print_log("Shift Unfroze", self.units[action['_id']].card.name, action['_id'])
          self.undos.append(self.shift_unfreeze(action['_id']))
        elif action['_id'] in self.apolloed:
          self.print_log("Shift Unapolloed", self.units[action['_id']].card.name, action['_id'])
          self.applyRevert(self.units[self.apolloer].reverts[-1])
          self.current_swipe_undos.append(None)
        elif self.units[action['_id']].side != self.player:
          self.print_log("Shift Start Breach", self.units[action['_id']].card.name, action['_id'])
          self.undos.append(self.do_breach(action["_id"], shift=True))
        elif self.units[action['_id']].built_this_turn:
          self.print_log("Shift unbuild", self.units[action['_id']].card.name, action['_id'])
          self.undos.append(self.shift_unbuild(action['_id']))
        elif self.units[action['_id']].clicked:
          self.print_log("Shift unclicked", self.units[action['_id']].card.name, action['_id'])
          self.undos.append(self.shift_unclick_unit(action['_id']))
        else:
          self.print_log("Shift clicked", self.units[action['_id']].card.name, action['_id'])
          if self.units[action['_id']].card.click.freeze != None:
            self.undos.append(self.shift_freeze_click(action['_id']))
          elif self.units[action['_id']].card.click.special in ["apollo", "kineticdriver"]:
            self.undos.append(self.shift_apollo_click(action['_id']))
          else:
            self.undos.append(self.shift_click_unit(action['_id']))
      elif action['_type'] == "card clicked":
        self.print_log("Purchased", self.cards[action['_id']].name, len(self.units))
        self.undos.append(self.buy(action['_id']))
      elif action['_type'] == "card shift clicked":
        self.undos.append(self.shift_buy(action["_id"]))
      elif action['_type'] == "space clicked":
        self.undos.append(self.advance_state())
      elif action['_type'] == "inst clicked":
        if self.units[action['_id']].side != self.player and not self.units[action['_id']].dead and self.units[action['_id']].card.frontline and self.units[action["_id"]].freeze == 0:
          self.print_log("Frontline Snipe", self.units[action['_id']].card.name, action['_id'])
          self.current_swipe_undos.append(self.frontline_snipe(action['_id']))
        elif self.final_breach == None and action['_id'] in self.died_frontline:
          self.print_log("Unfrontline Snipe", self.units[action['_id']].card.name, action['_id'])
          self.current_swipe_undos.append(self.unfrontline(action['_id']))
        elif self.breaching and self.units[action['_id']].side != self.player and not self.units[action['_id']].dead and self.final_breach == None:
          self.print_log("Breach Kill", self.units[action['_id']].card.name, action['_id'])
          assert not self.units[action['_id']].dead
          self.current_swipe_undos.append(self.breach_kill(action['_id']))
        elif self.breaching and self.units[action['_id']].side != self.player and self.units[action['_id']].is_blocking():
          self.print_log("End Breach", self.units[action['_id']].card.name, action['_id'])
          self.undos.append(self.end_breach())
        elif action['_id'] in self.apolloed:
          self.print_log("Unapolloed", self.units[action['_id']].card.name, action['_id'])
          self.applyRevert(self.units[self.apolloer].reverts[-1])
          self.current_swipe_undos.append(None)
        elif self.final_breach != None and self.breaching and self.units[action['_id']].side != self.player:
          self.print_log("Final Unbreach", action['_id'])
          self.undos.append(self.unbreach_kill(action['_id']))
        elif self.breaching and self.units[action['_id']].side != self.player:
          self.print_log("Unbreach Kill", self.units[action['_id']].card.name, action['_id'])
          self.current_swipe_undos.append(self.unbreach_kill(action['_id']))
        elif self.units[action['_id']].freeze > 0:
          self.print_log("Unfroze", self.units[action['_id']].card.name, action['_id'])
          self.current_swipe_undos.append(self.unfreeze(action['_id']))
        elif self.units[action['_id']].side != self.player and not (self.units[action['_id']].built_this_turn and self.units[action['_id']].master != None and self.units[self.units[action['_id']].master].side == self.player):
          self.print_log("Start Breach", self.units[action['_id']].card.name, action['_id'])
          if self.calc_opp_defence() == 0:
            self.current_swipe_undos.append(self.do_breach(action["_id"]))
          else:
            self.undos.append(self.do_breach(action["_id"]))
        elif self.units[action['_id']].built_this_turn:
          self.print_log("Unpurchased", self.units[action['_id']].card.name, action['_id'])
          self.undos.append(self.unbuild(action['_id']))
        elif self.units[action['_id']].clicked:
          self.print_log("Unclicked", self.units[action['_id']].card.name, action['_id'])
          assert (not self.units[action["_id"]].dead) or self.units[action["_id"]].card.click.delete or self.units[action["_id"]].card.click.hp_change < 0
          self.current_swipe_undos.append(self.unclick(action['_id']))
        else:
          self.print_log("Clicked", self.units[action['_id']].card.name, action['_id'])
          assert not self.units[action["_id"]].dead
          assert self.units[action["_id"]].side == self.player
          if self.units[action['_id']].card.click.freeze != None:
            self.undos.append(self.freeze_click(action['_id']))
          elif self.units[action['_id']].card.click.special in ["apollo", "kineticdriver"]:
            self.undos.append(self.apollo_click(action['_id']))
          else:
            self.current_swipe_undos.append(self.click_unit(action['_id']))
      elif action['_type'] == "end swipe processed":
        self.print_log("End Swipe")
        self.undos.append(UndoComposite(self.current_swipe_undos))
        assert self.current_swipe_undos != []
        self.current_swipe_undos = []
      else:
        raise Exception("Unimplemented action", action['_type'])
    elif self.state == "defend":
      if action['_type'] == "inst clicked":
        if self.final_defender != None and len(self.current_swipe_undos) == 0:
          # Final Undefending is normally not part of a swipe, but can be if final defending
          # and final undefending happen as part of the same motion
          self.print_log("Final Undefended", self.units[action['_id']].card.name, action['_id'])
          self.undos.append(self.undefend(action['_id']))
        elif action['_id'] in self.died_defending or self.final_defender == action['_id']:
          self.print_log("Undefended", self.units[action['_id']].card.name, action['_id'])
          self.current_swipe_undos.append(self.undefend(action['_id']))
        else:
          self.print_log("Defended", self.units[action['_id']].card.name, action['_id'])
          assert self.units[action['_id']].dead == False
          self.current_swipe_undos.append(self.defend(action['_id']))
      elif action['_type'] == "inst shift clicked":
        if action['_id'] in self.died_defending or action['_id'] == self.final_defender:
          self.print_log("Shift Undefended", self.units[action['_id']].card.name, action['_id'])
          self.undos.append(self.shift_undefend(action["_id"]))
        else:
          self.print_log("Shift Defended", self.units[action['_id']].card.name, action['_id'])
          self.undos.append(self.shift_defend(action['_id']))
      elif action['_type'] == "end swipe processed":
        self.print_log("End Swipe")
        self.undos.append(UndoComposite(self.current_swipe_undos))
        self.current_swipe_undos = []
      else:
        raise Exception("Unimplemented action", action['_type'])
    elif self.state == "commit":
      if action['_type'] in ["inst clicked", "card clicked", "inst shift clicked", "card shift clicked"]:
        self.print_log("Revert End Turn (clicking)")
        self.undos.pop().undo(self)
      else:
        raise Exception("Unimplemented action", action['_type'])
    else:
      raise Exception("Unimplemented action", action['_type'])
  
  def advance_state(self):
    if self.state == "buy":
      self.prev_state = self.state
      self.freezing = []
      self.apolloing = []
      self.state = "commit"
      self.print_log("End Turn")
      return(UndoAdvance(self.prev_state))
    elif self.state == "commit":
      self.print_log("Committed", self.turn ,self.p1res, len([unit for unit in self.units if unit.side == 1 and unit.dead == False]), self.p2res, len([unit for unit in self.units if unit.side == 2 and unit.dead == False]))
      self.undos = []
      self.print_units(self.player)
      if self.player == 1:
        self.player = 2
      else:
        self.player = 1
      if self.breaching:
        self.oppres[5] = 0
      self.defend_amt = self.oppres[5]
      self.ply += 1
      self.assembler.record_move(self)
      self.assembler.record_gamestate(self)
      for unit in self.units:
        unit.unstart = set()
      self.died_defending = set()
      self.final_defender = None
      self.apolloed = {}
      if self.oppres[5] == 0:
        self.state = "buy"
        self.start_turn()
      else:
        self.state = "defend"
    elif self.state == "defend":
      self.state = "buy"
      self.start_turn()
      self.print_log("Defended")
      if self.current_swipe_undos != []:
        self.undos.append(UndoComposite(self.current_swipe_undos))
      self.current_swipe_undos = []
      return UndoDefendComplete()
    else:
      raise Exception("Bad State")

def load_game(j, log_file=None):
  assert "eventInfo" not in j["logInfo"]["rawDeck"]
  assembler = model.Assembler(log_file)
  cards = [Card(c) for c in j['deckInfo']['mergedDeck']]
  
  assembler.record_setup(cards)
  
  s = State(cards, assembler, j["initInfo"]["initCards"][0], j["initInfo"]["initCards"][1], j["deckInfo"]["base"], j["initInfo"].get("infiniteSupplies", False))
  
  for action in j['commandInfo']['commandList']:
    ret = s.do_action(action)
    if ret != None:
      s = ret
    if len(s.units) > 150:
      s.print_log(s.units[150].is_blocking(), s.apolloed)
  
  return assembler.result().to_json()

if __name__ == "__main__":
  import sys
  load_game(sys.argv[1])
