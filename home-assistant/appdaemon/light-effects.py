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

input_select_effect_mode_states = { 'off': 'Aus', 'once': 'Einmal', 'loop': 'Loop' }

class LightsEffectsStars(hass.Hass):
    def initialize(self):
        self.log("Starting Lights Effects Stars")

        self.log(f"light entity: {self.args['light_entity']}, effect mode entity: {self.args['effect_mode_select_entity']}, effect type entity: {self.args['effect_type_select_entity']}")

        # update interval in s:
        self.time_interval_s = .5

        # the current time step as integer:
        self.time_step = 0

        self.effect_type = ''
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
        for effect_type in effects_definition:
            types += (effect_type, )
            
        self.call_service('input_select/set_options', entity_id=self.args['effect_type_select_entity'],
                              options=types)
        
        # setup callback functions when input select fields change:
        self.handle_effect_mode = self.listen_state(self.effect_mode_changed, self.args['effect_mode_select_entity'])
        self.handle_effect_type = self.listen_state(self.effect_type_changed, self.args['effect_type_select_entity'])

        # read effect type from input_select:
        self.effect_type = self.get_state(self.args['effect_type_select_entity'])

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

        # read initial effects definition:
        self.time_s, self.fp_brightness, self.f_color_rgb = self.read_effect_definition(effects_definition, self.effect_type)

    def read_effect_definition(self, effects_definition, effect_type):
        self.log(f"LightsEffectsStars: read_effect_definition: effect_type '{effect_type}'")

        # read vector with time instants:
        time_s = effects_definition[self.effect_type]['time_s']
        
        # read brightness value for each time step:
        fp_brightness = effects_definition[self.effect_type]['attributes']['brightness']

        if 'color_rgb' in effects_definition[self.effect_type]['attributes']:
            # read color_rgb value for each time step:
            y = effects_definition[self.effect_type]['attributes']['color_rgb']
            
            print(f'time_s: {time_s}, y: {y}')
            f_color_rgb = interpolate.interp1d(time_s, y, axis=0)
        else:
            f_color_rgb = None
            
        return time_s, fp_brightness, f_color_rgb
        
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
        if new in effects_definition:
            self.effect_type = new

        else:
            self.log(f"new state: {new} is not in list of effects, de-activating looping")

        # update initial effects definition:
        self.time_s, self.fp_brightness, self.f_color_rgb = self.read_effect_definition(effects_definition, self.effect_type)

    def loop(self, a):
        # current time:
        time_s = self.time_step * self.time_interval_s

        # new value:
        new_brightness = int(np.interp(time_s, self.time_s, self.fp_brightness) * 255)

        #state = self.get_state(self.args['light_entity'], attribute="all")
        self.log(f"LightsEffectsStars: looping. time_s: {time_s}, self.time_s[-1]: {self.time_s[-1]}. new_brightness: {new_brightness}")
        
        if self.f_color_rgb != None:
            #new_color_rgb = int(np.interp(time_s, self.time_s, self.fp_color_rgb) * 255)
            new_color_rgb = (self.f_color_rgb(time_s) * 255).astype(int)
            self.log(f"new_color_rgb: {new_color_rgb}")
                #self.set_state(self.args['light_entity'], state='on', attribute={'brightness': new_brightness} )
#            self.turn_on(self.args['light_entity'], brightness=new_brightness, rgb_color=[new_color_rgb[0], new_color_rgb[1], new_color_rgb[2]], 
#                     transition=1.2*self.time_interval_s)
            self.turn_on(self.args['light_entity'], rgb_color=[new_color_rgb[0], new_color_rgb[1], new_color_rgb[2]], 
                     transition=1.2*self.time_interval_s)
            self.turn_on(self.args['light_entity'], brightness=new_brightness, 
                         transition=1.2*self.time_interval_s)
        else:
            #self.set_state(self.args['light_entity'], state='on', attribute={'brightness': new_brightness} )
            self.turn_on(self.args['light_entity'], brightness=new_brightness, 
                         transition=1.2*self.time_interval_s)
            pass

        self.time_step += 1        
        print(f'time_s: {time_s}, self.time_s[-1]: {self.time_s[-1]}')
        if time_s >= self.time_s[-1]:
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
                self.time_step = 0
