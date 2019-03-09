import numpy as np
import pprint
import collections
import json
import datadiff

def res_to_str(res):
  s = str(res[0])
  for _ in res[1]:
    s += 'G'
  for _ in res[2]:
    s += 'B'
  for _ in res[3]:
    s += 'R'
  for _ in res[4]:
    s += 'E'
  for _ in res[5]:
    s += 'X'
  return s

def clean_dict(d):
  for k, n in list(d.items()):
    if n == 0:
      del d[k]

class InvalidMove(Exception):
  pass

class DIED(): pass

class Create():
  def __init__(self, card, own=True, buildtime=None, lifespan=None):
    self.card = card
    self.own = own
    self.buildtime = buildtime
    self.lifespan = lifespan
  
  def new(self, setup, purchasing=True):
    inst = setup.cards[self.card].new()
    if self.buildtime:
      if purchasing:
        inst.buildtime = self.buildtime
      else:
        inst.exhaust = self.buildtime
        inst.buildtime = 0
      if inst.buildtime != 0 or inst.exhaust != 0:
        inst.blocking = False
    else:
      if not purchasing:
        inst.exhaust = inst.buildtime
        inst.buildtime = 0
      if inst.buildtime != 0 or inst.exhaust != 0:
        inst.blocking = False
    if self.lifespan:
      inst.lifespan = self.lifespan
    return inst
  
  def to_json(self):
    j = { "card" : self.card
        , "own" : self.own
        }
    if self.buildtime != None:
      j["buildtime"] = self.buildtime
    if self.lifespan != None:
      j["lifespan"] = self.lifespan
    return j

class Effect():
  def __init__(self, res, sac=[], create=[], selfsac=False, hp_change=0, freeze=0, exhaust=0, resonate=None, special=None):
    self.res = res
    self.sac = sac
    self.create = create
    self.selfsac = selfsac
    self.hp_change = hp_change
    self.freeze = freeze
    self.exhaust = exhaust
    self.resonate = resonate
    self.special = special
  
  def to_json(self):
    return { "res" : self.res.tolist()
           , "sac" : self.sac
           , "create" : [c.to_json() for c in self.create]
           , "selfsac" : self.selfsac
           , "hp_change" : self.hp_change
           , "freeze" : self.freeze
           , "exhaust" : self.exhaust
           , "resonate" : self.resonate
           , "special" : self.special
           }

class Card():
  def __init__(self, name, toughness, max_hp, fragile, blocker, frontline, buildtime, lifespan, stamina, start_turn, click, buy, spell):
    self.name = name
    self.toughness = toughness
    self.max_hp = max_hp
    self.fragile = fragile
    self.blocker = blocker
    self.frontline = frontline
    self.buildtime = buildtime
    assert lifespan != 0
    self.lifespan = lifespan
    self.stamina = stamina
    self.start_turn = start_turn
    self.click = click
    self.buy = buy
    self.spell = spell
  
  def to_json(self):
    j = { "name" : self.name
        , "toughness" : self.toughness
        , "fragile" : self.fragile
        , "blocker" : self.blocker
        , "frontline " : self.frontline
        , "buildtime" : self.buildtime
        , "lifespan" : self.lifespan
        , "start_turn": self.start_turn.to_json()
        , "buy" : self.buy.to_json()
        , "spell" : self.spell
        }
    if self.click == None:
      j["click"] = None
    else:
      j["click"] = self.click.to_json()
    return j
  
  def new(self):
    if self.buildtime > 0:
      blocking = False
    else:
      blocking = self.blocker
    return Inst(self, blocking, self.toughness, self.lifespan, self.stamina, self.buildtime, 0)

class Inst():
  def __init__(self, card, blocking, health, lifespan, stamina, buildtime, exhaust):
    self.card = card
    self.blocking = blocking
    if buildtime > 0 or exhaust > 0:
      assert self.blocking == False
    self.lifespan = lifespan
    self.stamina = stamina
    self.buildtime = buildtime
    self.exhaust = exhaust
    
    self.health = health
    if not card.fragile:
      assert self.health == self.card.toughness
  
  def start_turn(self):
    if self.buildtime != 0:
      self.buildtime -= 1
    elif self.exhaust != 0:
      self.exhaust -= 1
    elif self.lifespan == 1:
      return DIED
    elif self.lifespan != None:
      self.lifespan -= 1
    
    if self.card.blocker and self.buildtime == 0 and self.exhaust == 0:
      self.blocking = True
    
    if self.exhaust == 0 and self.buildtime == 0:
      if self.card.blocker:
        self.blocking = True
      return self.card.start_turn
    else:
      return None
  
  def click(self):
    assert self.card.click != None
    self.blocking = False
    if self.stamina != None:
      assert self.stamina != 0
      self.stamina -= 1
    return self.card.click
  
  def __str__(self):
    props = [self.card.name]
    if self.card.blocker:
      if self.blocking:
        props.append("B")
      else:
        props.append("b")
    if self.card.fragile:
      props.append(str(self.health) + "hp")
      
    if self.lifespan == None:
      props.append("nls")
    else:
      props.append(str(self.lifespan) + "ls")
    
    if self.card.stamina != None:
      props.append(str(self.stamina) + "s")
    props.append(str(self.buildtime) + "bt")
    props.append(str(self.exhaust) + "e")
    return "_".join(props)
    

class Setup():
  def __init__(self, cards):
    self.cards = cards
  
  def to_json(self):
    return { "cards" : { k : v.to_json() for k, v in self.cards.items()}
           }
  
  def inst_from_str(self, s):
    props = s.split("_")
    card = self.cards[props.pop(0)]
    if card.blocker:
      blocking = props.pop(0) == "B"
    else:
      blocking = False
    if card.fragile:
      health = int(props.pop(0)[:-2])
    else:
      health = card.toughness
    ls_code = props.pop(0)
    if ls_code == "nls":
      lifespan = None
    else:
      lifespan = int(ls_code[:-2])
    if card.stamina != None:
      stamina = int(props.pop(0)[:-1])
    else:
      stamina = None
    buildtime = int(props.pop(0)[:-2])
    exhaust = int(props.pop(0)[:-1])
    return Inst(card, blocking, health, lifespan, stamina, buildtime, exhaust)

class GameState():
  def __init__(self, setup, p1, p2, ply, attack):
    self.setup = setup
    self.p1 = p1
    self.p2 = p2
    self.ply = ply
    self.attack = attack
    
  def to_json(self):
    return { "p1" : self.p1.to_json()
           , "p2" : self.p2.to_json()
           , "ply" : self.ply
           , "attack" : self.attack
           }
  
  @property
  def cur(self):
    if self.ply % 2 == 0:
      return self.p1
    else:
      return self.p2
  
  @property
  def opp(self):
    if self.ply % 2 == 0:
      return self.p2
    else:
      return self.p1
  
  def do_move(self, move):
    res = np.zeros(6, np.int)
    effects = []
    res[0] = self.cur.gold
    res[1] = self.cur.green
    cur_insts = self.cur.insts.copy()
    new_insts = collections.defaultdict(int)
    opp_insts = self.opp.insts.copy()
    new_opp_insts = collections.defaultdict(int)
    snipe_count = collections.defaultdict(int)
    freezes = collections.defaultdict(int)
    supplies = self.cur.supplies.copy()
    
    #Defend
    to_defend = self.attack
    for inst_str, n in move.defended.items():
      to_defend -= self.setup.inst_from_str(inst_str).health * n
      assert cur_insts[inst_str] >= n
      cur_insts[inst_str] -= n
    
    if move.final_defender == None:
      assert to_defend == 0
    else:
      inst = self.setup.inst_from_str(move.final_defender)
      assert to_defend > 0 and to_defend < inst.health
      assert move.final_defender in cur_insts
      if inst.card.fragile:
        cur_insts[str(inst)] -= 1
        inst.health -= to_defend
        cur_insts[str(inst)] += 1
      
    
    #Start Turn
    for (inst_str, n) in list(cur_insts.items()):
      cur_insts[inst_str] -= n
      inst = self.setup.inst_from_str(inst_str)
      effect = inst.start_turn()
      if effect != DIED:
        if effect != None:
          effects += [(effect, str(inst), False)] * n
          inst.health += effect.hp_change
          if inst.health > inst.card.max_hp:
            inst.health = inst.card.max_hp
          if not effect.selfsac and inst.health > 0:
            cur_insts[str(inst)] += n
        else:
          cur_insts[str(inst)] += n
    num_savior_drones = cur_insts["drone_b_nls_0bt_0e"] + cur_insts["drone_B_nls_0bt_0e"]
    
    #Click
    for (inst_str, n) in move.clicked.items():
      assert cur_insts[inst_str] >= n
      cur_insts[inst_str] -= n
      inst = self.setup.inst_from_str(inst_str)
      effect = inst.click()

      effects += [(effect, str(inst), False)] * n
      inst.health += effect.hp_change
      if inst.health > inst.card.max_hp:
        inst.health = inst.card.max_hp
      if not effect.selfsac and inst.health > 0:
         cur_insts[str(inst)] += n
    
    #Buy
    for (card_name, n) in move.bought.items():
      card = self.setup.cards[card_name]
      effects += [(card.buy, None, True)] * n
      if not card.spell:
        new_insts[str(card.new())] += n
      supplies[card.name] -= n
    
    #Apply Effects
    for (effect, source_inst_str, purchasing) in effects:
      res += effect.res
      #FIXME Do interesting effects
      for card_name in effect.sac:
        for inst_str in cur_insts:
          inst = self.setup.inst_from_str(inst_str)
          sacced = False
          if inst.card.name == card_name and (inst.blocking == False or inst.card.click == None) and inst.buildtime == 0 and inst.exhaust == 0 and cur_insts[inst_str] > 0:
            cur_insts[inst_str] -= 1
            sacced = True
            break
        assert sacced
      for create in effect.create:
        if create.own:
          new_insts[str(create.new(self.setup, purchasing))] += 1
        else:
          new_opp_insts[str(create.new(self.setup, purchasing))] += 1
      if effect.exhaust > 0:
        cur_insts[source_inst_str] -= 1
        inst = self.setup.inst_from_str(source_inst_str)
        inst.exhaust = effect.exhaust
        cur_insts[str(inst)] += 1
      if effect.freeze:
        freezes[effect.freeze] += 1
      
      if effect.resonate:
        for inst_str, n in cur_insts.items():
          inst = self.setup.inst_from_str(inst_str)
          if inst.card.name == effect.resonate and inst.buildtime == 0:
            res[5] += n
      
      if effect.special in ["apollo", "kineticdriver"]:
        snipe_count[effect.special] += 1
      elif effect.special == "deadeye":
        assert new_opp_insts["drone_b_nls_0bt_0e"] == 0
        if opp_insts["drone_b_nls_0bt_0e"] == 0:
          opp_insts["drone_b_nls_0bt_1e"] -= 1
        else:
          opp_insts["drone_b_nls_0bt_0e"] -= 1
      elif effect.special == "savior":
        res[0] += num_savior_drones
      elif effect.special != None:
        assert False
        
    
    assert np.all(res >= np.zeros(6, np.int))
    for snipe_type, snipes in move.sniped.items():
      assert len(snipes) == snipe_count[snipe_type]
    
    #Do Snipes
    for snipes in move.sniped.values():
      for snipe in snipes:
        opp_insts[snipe] -= 1
    
    #Add New Insts
    for inst_str, n in new_insts.items():
      cur_insts[inst_str] += n
    
    for inst_str, n in new_opp_insts.items():
      opp_insts[inst_str] += n
    
    #Freeze
    for inst_str, freeze_details in move.freeze.items():
      inst = self.setup.inst_from_str(inst_str)
      inst_nonblocking = self.setup.inst_from_str(inst_str)
      inst_nonblocking.blocking = False
      for freeze_detail in freeze_details:
        assert sum(freeze_detail) >= inst.health
      opp_insts[inst_str] -= len(freeze_details)
      opp_insts[str(inst_nonblocking)] += len(freeze_details)
    
    #Frontline
    for inst_str, n in move.frontlined.items():
      opp_insts[inst_str] -= n
      res[5] -= self.setup.inst_from_str(inst_str).health * n
    
    #Breach
    total_defence = 0
    for inst_str, n in opp_insts.items():
      inst = self.setup.inst_from_str(inst_str)
      if inst.blocking:
        total_defence += inst.health * n
    
    
    if total_defence <= res[5] and res[5] != 0:
      for inst_str, n in opp_insts.copy().items():
        inst = self.setup.inst_from_str(inst_str)
        if inst.blocking:
          assert move.breached[inst_str] == n
          opp_insts[inst_str] = 0
          res[5] -= inst.health * n
        else:
          opp_insts[inst_str] -= move.breached[inst_str]
          res[5] -= inst.health * move.breached[inst_str]
      
      if move.final_breach != None:
        opp_insts[move.final_breach] -= 1
        inst = self.setup.inst_from_str(move.final_breach)
        assert inst.card.fragile
        inst.health -= res[5]
        opp_insts[str(inst)] += 1
        res[5] = 0
      
      assert res[5] == 0 or all(n == 0 for n in opp_insts.values()) or all(self.setup.inst_from_str(inst_str).health > res[5] or n == 0 or self.setup.inst_from_str(inst_str).buildtime > 0 for inst_str, n in opp_insts.items()) #WRONG
      res[5] = 0
          
    
    cur = Side(int(res[0]), int(res[1]), cur_insts, supplies)
    opp = Side(self.opp.gold, self.opp.green, opp_insts, self.opp.supplies)
    
    if self.ply % 2 == 0:
      return GameState(self.setup, cur, opp, self.ply+1, int(res[5]))
    else:
      return GameState(self.setup, opp, cur, self.ply+1, int(res[5]))

class Side():
  def __init__(self, gold, green, insts, supplies):
    self.gold = gold
    self.green = green
    self.insts = insts
    self.supplies = supplies

  def to_json(self):
    clean_dict(self.insts)
    return { "gold" : self.gold
           , "green" : self.green
           , "insts" : dict(self.insts)
           , "supplies" : dict(self.supplies)
           }

class Move():
  def __init__(self, bought, clicked, defended, final_defender, breached, final_breach, frontlined, freeze, sniped):
    self.bought = bought
    self.clicked = clicked
    self.defended = defended
    self.final_defender = final_defender
    self.breached = breached
    self.final_breach = final_breach
    self.frontlined = frontlined
    self.freeze = freeze
    self.sniped = sniped
  
  def to_json(self):
    clean_dict(self.bought)
    clean_dict(self.clicked)
    clean_dict(self.defended)
    clean_dict(self.breached)
    clean_dict(self.frontlined)
    clean_dict(self.freeze)
    return { "bought" : dict(self.bought)
           , "clicked" : dict(self.clicked)
           , "defended" : dict(self.defended)
           , "final_defender" : self.final_defender
           , "breached" : dict(self.breached)
           , "final_breach" : self.final_breach
           , "frontlined" : dict(self.frontlined)
           , "freeze" : dict(self.freeze)
           , "sniped" : self.sniped
           }

class Game():
  def __init__(self, setup, states, moves):
    self.setup = setup
    self.states = states
    self.moves = moves
  
  def to_json(self):
    return { "setup" : self.setup.to_json()
           , "states" : [s.to_json() for s in self.states]
           , "moves" : [m.to_json() for m in self.moves]
           }

class Assembler():
  def __init__(self, log_file=None):
    self.log_file = log_file
    
    self.game_states = []
    self.moves = []
  
  def __deepcopy__(self, memo):
    return self
  
  def log(self, obj):
    if self.log_file:
      pprint.pprint(obj, self.log_file, indent = 2)
      self.log_file.write("\n")
      self.log_file.flush()
  
  def log_plain(self, s):
    if self.log_file:
      self.log_file.write(s)
      self.log_file.write("\n")
      self.log_file.flush()
  
  def assemble_effect(self, leffect):
    sac = [n.lower().replace(" ", "") for n in leffect.sac]
    create = []
    for lcreate in leffect.create:
      if lcreate.buildtime == 0:
        bt = None
      else:
        bt = lcreate.buildtime
      c = Create(lcreate.unit_name.lower().replace(" ", ""), not lcreate.opponent, bt, lcreate.lifespan)
      for _ in range(lcreate.number):
        create.append(c)
    
    if leffect.exhaust == None:
      exhaust = 0
    else:
      exhaust = leffect.exhaust
    
    if leffect.freeze != None:
      freeze = leffect.freeze
    else:
      freeze = 0
    
    if leffect.resonate != None:
      resonate = leffect.resonate.lower().replace(" ", "")
    else:
      resonate = None
    
    return Effect(leffect.res, sac, create, leffect.delete, leffect.hp_change, freeze, exhaust, resonate, leffect.special)
  
  def unit_to_inst(self, unit):
    card = self.setup.cards[unit.card.name.lower().replace(" ", "")]
    if card.blocker and unit.buildtime == 0 and unit.exhaust == 0 and unit.freeze < unit.health:
      blocking = not unit.clicked
    else:
      blocking = False
    return Inst(card, blocking, unit.health, unit.lifespan, unit.stamina, unit.buildtime, unit.exhaust)
  
  def record_setup(self, lcards):
    cards = {}
    for lcard in lcards:
      name = lcard.name.lower().replace(" ", "")
      if lcard.click:
        click = self.assemble_effect(lcard.click)
      else:
        click = None
      cards[name] = Card(name, lcard.toughness, lcard.max_hp, lcard.fragile, lcard.blocker, lcard.frontline, lcard.buildtime, lcard.lifespan, lcard.stamina, self.assemble_effect(lcard.start_turn), click, self.assemble_effect(lcard.buy), lcard.spell)
    
    self.setup = Setup(cards)
    
    self.log(self.setup.to_json())
  
  def record_move(self, state):
    bought = collections.defaultdict(int)
    for name, n in state.bought.items():
      bought[name.lower().replace(" ", "")] += n
    
    clicked = collections.defaultdict(int)
    for _id in state.clicked:
      inst = self.unit_to_inst(state.units[_id])
      # We have undo the effects of the click here to get the preclick inst
      if inst.card.blocker:
        inst.blocking = True
      inst.exhaust = 0
      if inst.stamina != None:
        inst.stamina += 1
      inst.health = state.units[_id].pre_click_health
      clicked[str(inst)] += 1
    
    defended = collections.defaultdict(int)
    for _id in state.died_defending:
      defended[str(self.unit_to_inst(state.units[_id]))] += 1
    
    if state.final_defender != None:
      inst = self.unit_to_inst(state.units[state.final_defender])
      if inst.card.fragile:
        inst.health = state.units[state.final_defender].start_turn_health
        inst.health += state.absorb_amt
      if inst.lifespan != None:
        inst.lifespan += 1
      if not inst.blocking:
        inst.blocking = True
        inst.exhaust = 0
        if inst.stamina != None:
          inst.stamina += 1
      final_defender = str(inst)
    else:
      final_defender = None
    
    breached = collections.defaultdict(int)
    for _id in state.died_breach:
      unit = state.units[_id]
      inst = self.unit_to_inst(unit)
      inst.blocking = unit.card.blocker and unit.buildtime == 0 and unit.exhaust == 0 and not unit.clicked
      breached[str(inst)] += 1
    
    if state.final_breach != None:
      final_breach_inst = self.unit_to_inst(state.units[state.final_breach])
      final_breach_inst.health += state.final_breach_amt
      final_breach = str(final_breach_inst)
    else:
      final_breach = None
    
    freeze = collections.defaultdict(list)
    for unit_id, unit in enumerate(state.units):
      if not unit.dead and not unit.card.spell and unit.freeze >= unit.health:
        freeze_list = []
        for _id in unit.freeze_sources:
          freeze_list.append(state.units[_id].card.click.freeze)
        inst = self.unit_to_inst(unit)
        inst.blocking = True # Get the prefreeze inst_str
        if unit_id == state.final_breach:
          inst.health += state.final_breach_amt
        freeze[str(inst)].append(freeze_list)
    
    frontlined = collections.defaultdict(int)
    for _id in state.died_frontline:
      unit = state.units[_id]
      inst = self.unit_to_inst(unit)
      inst.blocking = unit.card.blocker and unit.buildtime == 0 and unit.exhaust == 0 and not unit.clicked
      frontlined[str(inst)] += 1
    
    sniped = collections.defaultdict(list)
    
    for snipee, sniper in state.apolloed.items():
      sniped[state.units[sniper].card.click.special].append(str(self.unit_to_inst(state.units[snipee])))
    
    m = Move(bought, clicked, defended, final_defender, breached, final_breach, frontlined, freeze, sniped)
    self.moves.append(m)
    
    self.log(m.to_json())
  
  def record_gamestate(self, state):
    p1insts = collections.defaultdict(int)
    p2insts = collections.defaultdict(int)
    for unit in state.units:
      if not unit.dead and not unit.card.spell:
        inst = self.unit_to_inst(unit)
        if unit.side == 1:
          p1insts[str(inst)] += 1
        else:
          p2insts[str(inst)] += 1
    
    p1supplies = { n.lower().replace(" ", "") : sup for (n, sup) in state.p1supplies.items() }
    p2supplies = { n.lower().replace(" ", "") : sup for (n, sup) in state.p2supplies.items() }
    
    p1 = Side(int(state.p1res[0]), int(state.p1res[1]), p1insts, p1supplies)
    p2 = Side(int(state.p2res[0]), int(state.p2res[1]), p2insts, p2supplies)
    
    gs = GameState(self.setup, p1, p2, state.ply, int(state.oppres[5]))
    self.game_states.append(gs)
    
    self.log(gs.to_json())
    
    if len(self.game_states) > 1:
      gs2 = self.game_states[-2].do_move(self.moves[-1])
      if gs2.to_json() != gs.to_json():
        self.log(gs2.to_json())
        self.log_plain(str(datadiff.diff(gs.to_json(), gs2.to_json())))
        assert False
  
  def result(self):
    return Game(self.setup, self.game_states, self.moves)
