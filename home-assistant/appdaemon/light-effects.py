#!/usr/bin/env python3
# \author fms13
# \date December 26, 2020
#
# \brief Provides effects for lights like automatic color and brightness changes
#  Python script to be used together with Home Assistant and Appdaemon.
#
# Under development.

import hassapi as hass
import datetime
import numpy as np
from scipy import interpolate

# state of a white ambiance lamp:
# state: {'entity_id': 'light.stern_wohnzimmer', 'state': 'on',
# 'attributes': {'min_mireds': 250, 'max_mireds': 454, 'brightness': 102, 'color_temp': 388

# state of color lamp:
# state: {'entity_id': 'light.tipi', 'state': 'on', 'attributes': {'effect_list': ['colorloop', 'random'],
# 'brightness': 200, 'hs_color': [50.597, 52.549], 'rgb_color': [255, 233, 121], 'xy_color': [0.431, 0.439],
# 'effect': 'none', 'friendly_name': 'Zeltlampe', 'supported_features': 61}

# definitions of the effects:
effects_definition = dict()

# smooth on and off for a light:
effects_definition['Sparkle-Up'] = {
    'time_s': [ 0.0, 2.0, 4.0 ],
    'attributes': {
        'brightness': [ 0.0, 1.0, 0.0 ],
        }
    }

# changes a light color from red over green to blue:
effects_definition['RGB-Color-Wheel'] = { 
    'time_s': [ 0.0, 4.0, 8.0 ],
    'attributes': {
        'brightness': [ 1.0, 1.0, 1.0 ],
        'color_rgb': [
            [ 1.0, 0.0, 0.0 ],
            [ 0.0, 1.0, 0.0 ],
            [ 0.0, 0.0, 1.0 ]
            ]
        }
    }

# Underwater World: a bit of green, then changes between blue and white:
effects_definition['Underwater World'] = { 
    'time_s': [ 0.0, 1.0, 3.0, 6.0, 9.0, 11.0, 13.0 ],
    'attributes': {
        'brightness': [ 1.0, 1.0, 1.0, 0.0, 1.0, 1.0, 1.0],
        'color_rgb': [
            [ 0.0, 1.0, 0.0 ],
            [ 0.0, 0.0, 1.0 ],
            [ 1.0, 1.0, 1.0 ],
            [ 1.0, 1.0, 1.0 ],
            [ 0.0, 0.0, 1.0 ],
            [ 1.0, 1.0, 1.0 ],
            [ 0.0, 0.0, 1.0 ]
            ]
        }
    }

# effect definitions for multiple entities:
effects_definition_multiple_entities = dict()
effects_definition_multiple_entities['Sparkle-Ups'] = {
    'effects': ('Sparkle-Up', 'Sparkle-Up'),
    'delays': (0.0, 1.0)
    }

effects_definition_multiple_entities['Underwater Worlds'] = {
    'effects': ('Underwater World', 'Underwater World'),
    'delays': (0.0, 1.0)
    }

input_select_effect_mode_states = { 'off': 'Aus', 'once': 'Einmal', 'loop': 'Loop' }

class EffectForLight:
    def __init__(self, light_entity, initial_effect_type):
        self.light_entity = light_entity

        # read initial effects definition:
        self.read_effect_definition(effects_definition, initial_effect_type)

    def get_light_entity(self):
        return self.light_entity
    
    def get_max_time(self):
        return self.time_s[-1]
    
    def read_effect_definition(self, effects_definition, effect_type):
        print(f"read_effect_definition: entity: {self.light_entity}, new effect_type '{effect_type}'")

        # read vector with time instants:
        self.time_s = effects_definition[effect_type]['time_s']
        
        # read brightness value for each time step:
        self.fp_brightness = effects_definition[effect_type]['attributes']['brightness']

        if 'color_rgb' in effects_definition[effect_type]['attributes']:
            # read color_rgb value for each time step:
            y = effects_definition[effect_type]['attributes']['color_rgb']
            
            print(f'self.time_s: {self.time_s}, y: {y}')
            self.f_color_rgb = interpolate.interp1d(self.time_s, y, axis=0)
        else:
            self.f_color_rgb = None
            
    def get_state_for_time_instant(self, infinite_time_s):
        # infinite_time_s can grow infinitely, we limit it to the maximum time of the 
        # current effect:
        time_s = infinite_time_s % self.time_s[-1]
        
        # compute new brightness value:
        new_brightness = int(np.interp(time_s, self.time_s, self.fp_brightness) * 255)

        # compute new rgb color value if rgb_color is defined for this effect:
        if self.f_color_rgb == None:
            new_color_rgb = None
        else:
            #new_color_rgb = int(np.interp(time_s, self.time_s, self.fp_color_rgb) * 255)
            new_color_rgb = (self.f_color_rgb(time_s) * 255).astype(int)
            print(f"new_color_rgb: {new_color_rgb}")
        
        return new_brightness, new_color_rgb

class LightsEffectsStars(hass.Hass):
    def initialize(self):
        self.log("Starting Lights Effects Stars")

        # read entities:
        light_entities = self.split_device_list(self.args["light_entities"]) 
        self.log(f"light entities: {light_entities}, effect mode input_select: {self.args['effect_mode_select_entity']}, effect type input_select: {self.args['effect_type_select_entity']}")

        # update interval in s:
        self.time_interval_s = .5

        # the current time step as integer:
        self.time_step = 0

        self.f_color_rgb = None
        
        self.loop_handle = None
        # populate states for effect mode input_select:
        modes = ()
        for item in input_select_effect_mode_states:
            modes += (input_select_effect_mode_states[item], )
            
        self.call_service('input_select/set_options', entity_id=self.args['effect_mode_select_entity'],
                              options=modes)

        # populate effect types for effect type input_select:
        types = ()
        if len(light_entities) == 1:
            # if there's only one entity, list the effects for one light entity:
            for effect_type in effects_definition:
                types += (effect_type, )
        else:
            # list the effects for multiple light entities:
            for effect_type in effects_definition_multiple_entities:
                types += (effect_type, )
            
        self.call_service('input_select/set_options', entity_id=self.args['effect_type_select_entity'],
                              options=types)
        
        # setup callback functions when input select fields change:
        self.handle_effect_mode = self.listen_state(self.effect_mode_changed, self.args['effect_mode_select_entity'])
        self.handle_effect_type = self.listen_state(self.effect_type_changed, self.args['effect_type_select_entity'])

        # read state from input_select:
        self.state = ''
        self.effect_mode = self.get_state(self.args['effect_mode_select_entity'])
        if self.effect_mode == 'Aus':
            self.state = 'off'
        elif self.effect_mode == 'Einmal':
            self.state = 'once'
        elif self.effect_mode == 'Loop':
            self.state = 'loop'
        else:
            self.state = 'off'
            self.log(f"LightsEffectsStars: ERROR: unknown effect state '{self.effect_mode}'")
        
        # read effect type from input_select:
        effect_type = self.get_state(self.args['effect_type_select_entity'])

        # setup objects for all entities:
        self.effects_for_lights = ()
        if len(light_entities) == 1:
            # one light entity:
            self.effects_for_lights += (EffectForLight(light_entities[0], effect_type), )
        else:
            # multiple light entities:
            for k, light_entity in enumerate(light_entities):
                self.effects_for_lights += (EffectForLight(light_entity, effects_definition_multiple_entities[effect_type]['effects'][k]), )
            
    def effect_mode_changed(self, entity, attribute, old, new, kwargs):
        self.log(f"LightsEffectsStars: new effect mode: {new}")
        if new in ('Aus', 'Einmal', 'Loop'):
            if new == 'Aus':
                self.state = 'off'
                self.time_step = 0
                
                if self.loop_handle != None:
                    self.cancel_timer(self.loop_handle)
                    
            elif new == 'Einmal':
                self.state = 'once'
                self.log(f"new mode: {new}, run effect once")
                self.loop_handle = self.run_every(self.loop, "now", self.time_interval_s)
            elif new == 'Loop':
                self.state = 'loop'
                self.log(f"new mode: {new}, activating looping")
                self.loop_handle = self.run_every(self.loop, "now", self.time_interval_s)
                            
    def effect_type_changed(self, entity, attribute, old, new, kwargs):
        self.log(f"LightsEffectsStars: new effect type: {new}")

        # update effects definitions:
        if len(self.effects_for_lights) == 1:
            # one light entity:
            if new not in effects_definition:
                self.log(f"new state: {new} is not in list of effects for single light entities, de-activating looping")
                # TODO

            self.effects_for_lights[0].read_effect_definition(effects_definition, new)
        else:
            # multiple light entities:
            if new not in effects_definition_multiple_entities:
                self.log(f"new state: {new} is not in list of effects for multiple light entities, de-activating looping")
                # TODO

            for k, effect_for_light in enumerate(self.effects_for_lights):
                effect_for_light.read_effect_definition(effects_definition, effects_definition_multiple_entities[new]['effects'][k])

    def loop(self, a):
        # current time:
        time_s = self.time_step * self.time_interval_s

        # for all light entities:
        max_time = 0.0
        for effect_for_light in self.effects_for_lights:
            # compute maximum time of all effects:
            if effect_for_light.get_max_time() > max_time:
                max_time = effect_for_light.get_max_time() 
                
            light_entity = effect_for_light.get_light_entity()
             
            # get new values for this time:
            new_brightness, new_color_rgb = effect_for_light.get_state_for_time_instant(time_s)
            
            self.log(f"time_s: {time_s}, new_brightness: {new_brightness}, new_color_rgb: {new_color_rgb}")

            if new_color_rgb.any() != None:
                    #self.set_state(self.args['light_entity'], state='on', attribute={'brightness': new_brightness} )
    #            self.turn_on(self.args['light_entity'], brightness=new_brightness, rgb_color=[new_color_rgb[0], new_color_rgb[1], new_color_rgb[2]], 
    #                     transition=1.2*self.time_interval_s)
                self.turn_on(light_entity, rgb_color=[new_color_rgb[0], new_color_rgb[1], new_color_rgb[2]], 
                         transition=1.2*self.time_interval_s)
            
            if new_brightness != None:
                self.turn_on(light_entity, brightness=new_brightness, 
                             transition=1.2*self.time_interval_s)
    
            else:
                #self.set_state(self.args['light_entity'], state='on', attribute={'brightness': new_brightness} )
                self.turn_on(light_entity, brightness=new_brightness, 
                             transition=1.2*self.time_interval_s)
                    
        self.time_step += 1        
        #print(f'time_s: {time_s}, self.time_s[-1]: {self.time_s[-1]}')
        if time_s >= max_time:
            if self.state == 'off':
                # go to state off:
                self.cancel_timer(self.loop_handle)
                self.time_step = 0
            elif self.state == 'once':
                # go to state off:
                self.state == 'off'
                self.time_step = 0
                self.call_service('input_select/select_option', entity_id=self.args['effect_mode_select_entity'],
                      option=input_select_effect_mode_states['off'])

                self.cancel_timer(self.loop_handle)
            elif self.state == 'loop':
                # do nothing, let time grow
                pass
