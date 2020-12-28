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
from time import sleep
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
effects_definition['Dark-to-Bright'] = {
    'time_s': [ 0.0, 2.0, 4.0 ],
    'attributes': {
        'brightness': [ 0.0, 1.0, 0.0 ],
        }
    }

# smooth on and off for a light, change color temperature:
effects_definition['Sparkle-Up'] = {
    'time_s': [ 0.0, 2.0, 3.0, 5.0 ],
    'attributes': {
        'brightness': [ 0.0, 1.0, 1.0, 0.0 ],
        'color_temp': [ 454.0, 250.0, 250.0, 454.0 ],
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
    'delays': (0.0, 2.0)
    }

effects_definition_multiple_entities['Underwater Worlds'] = {
    'effects': ('Underwater World', 'Underwater World'),
    'delays': (0.0, 3.0)
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

        # read color_temp value for each time step:
        if 'color_temp' in effects_definition[effect_type]['attributes']:
            self.fp_color_temp = effects_definition[effect_type]['attributes']['color_temp']
        else:
            self.fp_color_temp = None

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

        # compute new brightness value:
        if self.fp_color_temp != None:
            new_color_temp = int(np.interp(time_s, self.time_s, self.fp_color_temp))
        else:
            new_color_temp = None
            
        # compute new rgb color value if rgb_color is defined for this effect:
        if self.f_color_rgb == None:
            new_color_rgb = np.array([None, None, None ])
        else:
            #new_color_rgb = int(np.interp(time_s, self.time_s, self.fp_color_rgb) * 255)
            new_color_rgb = (self.f_color_rgb(time_s) * 255).astype(int)
            print(f"new_color_rgb: {new_color_rgb}")
        
        return new_brightness, new_color_rgb, new_color_temp

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

        #self.f_color_rgb = None
        
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
            self.offset_s = (0.0, )
        else:
            # multiple light entities:
            for k, light_entity in enumerate(light_entities):
                self.effects_for_lights += (EffectForLight(light_entity, effects_definition_multiple_entities[effect_type]['effects'][k]), )
                
            self.offset_s = effects_definition_multiple_entities[effect_type]['delays']
    
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

            self.offset_s = effects_definition_multiple_entities[new]['delays']
            
    def loop(self, a):
        # current time:
        time_s = self.time_step * self.time_interval_s

        # for all light entities:
        max_time = 0.0
        for k, effect_for_light in enumerate(self.effects_for_lights):
            # compute maximum time of all effects:
            if effect_for_light.get_max_time() > max_time:
                max_time = effect_for_light.get_max_time() 
                
            light_entity = effect_for_light.get_light_entity()
                
            # get new values for this time:
            new_brightness, new_color_rgb, new_color_temp = effect_for_light.get_state_for_time_instant(time_s + self.offset_s[k])
            
            self.log(f"time_s: {time_s}, new_brightness: {new_brightness}, new_color_rgb: {new_color_rgb}, new_color_temp: {new_color_temp}")

            # crete dict with keyword arguments for brightness, rgb color and color termperature
            # to be set in self.turn_on below:
            parameters = {}
            # was brightness provided by get_state_for_time_instant?
            if new_brightness != None:
                # if brightness was provided, add it to keyword arguments:
                parameters['brightness'] = f'{new_brightness}'

            # if-elif: add either color_rgb or color_temp, never both:
            # was color_rgb provided by get_state_for_time_instant?
            if new_color_rgb.all() != None:
                parameters['rgb_color'] = [f'{new_color_rgb[0]}', f'{new_color_rgb[1]}', f'{new_color_rgb[2]}' ]

                # set brightness and rgb color with one call:
                self.turn_on(light_entity, **parameters, transition=1.2*self.time_interval_s)

            # if not, was color temperature provided by get_state_for_time_instant?
            elif new_color_temp != None:
                # set both at same time:
                parameters['color_temp'] = f'{new_color_temp}'
                self.turn_on(light_entity, **parameters, transition=1.2*self.time_interval_s)

                # setting both brightness and color temperature does not work for Tradfri lights:                
                # 'I encountered a problem when trying to set both the brightness and the color temperature in a Home Assistant service call (light.turn_on). Apparently, the Tradfri bulbs only respond to one of these values at a time.':
                # https://www.wouterbulten.nl/blog/tech/ikea-tradfri-temp-and-brightness-with-home-assistant/

                # setting the two values with two calls does not look well for our animations:
                #print(f'setting color_temp to {new_color_temp}')
                #self.turn_on(light_entity, color_temp=f'{new_color_temp}', transition=0.2*self.time_interval_s)
                #sleep(0.3*self.time_interval_s)
                # set brightness at .5 transition time:
                #print(f'setting brightness to {parameters}')
                #self.turn_on(light_entity, **parameters, transition=0.7*self.time_interval_s)
                
            else:
                # only set brightness:
                self.turn_on(light_entity, **parameters, transition=1.2*self.time_interval_s)
                    
        # increment time step integer:                    
        self.time_step += 1        

        # is the aninmation over? for multiple animations? is the longest over?:
        if time_s >= max_time:
            # yes:
            if self.state == 'off':
                # go to state off:
                # if we're here, the timer might still be running, cancel it again:
                self.cancel_timer(self.loop_handle)
                self.time_step = 0
                self.call_service('input_select/select_option', entity_id=self.args['effect_mode_select_entity'],
                      option=input_select_effect_mode_states['off'])
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
