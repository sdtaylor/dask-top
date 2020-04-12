#!/usr/bin/python

# Copyright (C) 2017 Alex Manuskin, Gil Tsuker
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# This implementation was inspired by Ian Ward
# Urwid web site: http://excess.org/urwid/

"""An urwid program to stress and monitor you computer"""

from __future__ import print_function

import urwid
from ComplexBarGraphs import ScalableBarGraph
from ComplexBarGraphs import LabeledBarGraph
from HelpMenu import HelpMenu

from dask.distributed import Client

import psutil
import time
import subprocess
import ctypes
import os
import argparse
import logging
from aux import read_msr

# Constants
UPDATE_INTERVAL = 0.2
DEGREE_SIGN = u'\N{DEGREE SIGN}'
TURBO_MSR = 429
WAIT_SAMPLES = 5

log_file = "_s-tui.log"

VERSION = 0.1
VERSION_MESSAGE = " s-tui " + str(VERSION) +\
                  " - (C) 2017 Alex Manuskin, Gil Tsuker\n\
                  Relased under GNU GPLv2"

# globals

INTRO_MESSAGE = "\
********s-tui manual********\n\
-Alex Manuskin      alex.manuskin@gmail.com\n\
-Gil Tsuker         \n\
April 2017\n\
\n\
s-tui is a terminal UI add-on for stress. The software uses stress to run CPU\
hogs, while monitoring the CPU usage, temperature and frequency.\n\
The software was conceived with the vision of being able to stress test your\
computer without the need for a GUI\n\
"

class GraphData:
    THRESHOLD_TEMP = 80

    def __init__(self, graph_num_bars, dask_address):
        self.dask_client = Client(address = dask_address)        
        
        self.currentValue = {'Memory' :{'total_memory':0,
                                        'used_memory':0},
                             'CPU'    :{'cpu_usage':0},
                             'Cluster':{'n_workers':0,
                                        'total_threads':0},
                             'Workers':[]}
        self.update_dask_values()
        
        # Constants data
        self.mem_max_value = self.currentValue['Memory']['total_memory']
        self.util_max_value = 100
        self.graph_num_bars = graph_num_bars
        
        # Data for graphs
        self.cpu_util = [0] * graph_num_bars
        self.mem_util = [0] * graph_num_bars
        # Data for statistics
        self.n_workers = self.num_workers()
        self.total_mem = self.currentValue['Memory']['total_memory']
        self.used_mem  = self.currentValue['Memory']['used_memory']
                


    def update_all(self):
        self.update_dask_values()
        
        self.n_workers = self.num_workers()
        self.mem_max_value = self.currentValue['Memory']['total_memory']
        self.total_mem  = self.currentValue['Memory']['total_memory']
        self.used_mem      = self.currentValue['Memory']['used_memory']
        
        self.cpu_util = self.update_graph_val(self.cpu_util, self.cpu_usage())
        self.mem_util = self.update_graph_val(self.mem_util, self.used_mem)
        
        
    def reset(self):
        self.cpu_util = [0] * self.graph_num_bars
        self.mem_util = [0] * self.graph_num_bars
        
        self.mem_max_value = 0
        self.total_mem  = 0
        self.used_mem      = 0

    def update_graph_val(self, values, new_val):
        values_num = len(values)

        if values_num > self.graph_num_bars:
            values = values[values_num - self.graph_num_bars - 1:]
        elif values_num < self.graph_num_bars:
            zero_pad = [0] * (self.graph_num_bars - values_num)
            values = zero_pad + values

        values.append(new_val)
        return values[1:]

    def update_dask_values(self):
            self.worker_info = self.dask_client.scheduler_info()['workers']
            self.currentValue['Memory']['total_memory'] = round(self.available_memory() / (1024**2),2)
            self.currentValue['Memory']['used_memory']  = round(self.used_memory() / (1024**2),2)
            self.currentValue['Memory']['used_memory_percent']  = self.currentValue['Memory']['used_memory'] / self.currentValue['Memory']['total_memory']
            self.currentValue['CPU']['cpu_usage'] = self.cpu_usage()
            self.currentValue['Cluster']['n_workers'] = self.num_workers()
            self.currentValue['Cluster']['total_threads'] = self.num_workers()
            self.currentValue['Workers'] = self.get_worker_stats()
        
    def num_workers(self):
        return len(self.worker_info)
    
    def num_threads(self):
        threads = [worker['nthreads'] for _, worker in self.worker_info.items()]
        return(sum(threads))
    
    def available_memory(self):
        tots = 0
        for w, info in self.worker_info.items():
            tots += info['memory_limit']
        return tots
    
    def used_memory(self):
        tots = 0
        for w, info in self.worker_info.items():
            tots += info['metrics']['memory']
        return tots
    
    def get_worker_stats(self):
        worker_stats=[]
        for w, info in self.worker_info.items():
            stats = {'user':'filler',
                     'id' : 'filler',
                     'name' : 'filler',
                     'rawtime':1,
                     'time':1,
                     'command':'',
                     'cpu':1,
                     'memory':1,
                     'local_ports':'filler'}
            stats['address'] = w
            stats['nthreads'] = info['nthreads']
            stats['memory']   = round(info['metrics']['memory'] / (1024**2),2)
            stats['memory_limit'] = round(info['memory_limit'] / (1024**2), 2)
            stats['cpu']      = info['metrics']['cpu'] 
            stats['read']     =  round(info['metrics']['read_bytes'] / (1024**2), 2)
            stats['write']     = round(info['metrics']['write_bytes'] / (1024**2), 2)
            
            worker_stats.append(stats)
        return worker_stats
    
    def cpu_usage(self):
        """ 
        Average cpu utilization across all workers
        """
        usages = []
        for w, info in self.worker_info.items():
            usages.append(info['metrics']['cpu'])
        if len(usages)>0:
            return sum(usages) / len(usages)
        else:
            return 0

class GraphView(urwid.WidgetPlaceholder):
    """
    A class responsible for providing the application's interface and
    graph display.
    """

    palette = [
        ('body',                    'black',          'light gray',   'standout'),
        ('header',                  'white',          'dark red',     'bold'),
        ('screen edge',             'light blue',     'brown'),
        ('main shadow',             'dark gray',      'black'),
        ('line',                    'black',          'light gray',   'standout'),
        ('menu button',             'light gray',     'black'),
        ('bg background',           'light gray',     'black'),
        ('util light',              'black',          'dark green',   'standout'),
        ('util light smooth',       'dark green',     'black'),
        ('util dark',               'dark red',       'light green',  'standout'),
        ('util dark smooth',        'light green',    'black'),
        ('high temp dark',          'light red',      'dark red',     'standout'),
        ('overheat dark',           'black',          'light red',     'standout'),
        ('high temp dark smooth',   'dark red',       'black'),
        ('high temp light',         'dark red',       'light red',    'standout'),
        ('high temp light smooth',  'light red',      'black'),
        ('temp dark',               'black',          'dark cyan',    'standout'),
        ('temp dark smooth',        'dark cyan',      'black'),
        ('temp light',              'dark red',       'light cyan',   'standout'),
        ('temp light smooth',       'light cyan',     'black'),
        ('freq dark',               'dark red',       'dark magenta', 'standout'),
        ('freq dark smooth',        'dark magenta',   'black'),
        ('freq light',              'dark red',       'light magenta', 'standout'),
        ('freq light smooth',       'light magenta',  'black'),
        ('button normal',           'light gray',     'dark blue',    'standout'),
        ('button select',           'white',          'dark green'),
        ('line',                    'black',          'light gray',   'standout'),
        ('pg normal',               'white',          'black',        'standout'),
        ('pg complete',             'white',          'dark magenta'),
        ('high temp txt',           'light red',      'light gray'),
        ('pg smooth',               'dark magenta',   'black')
        ]

    GRAPH_OFFSET_PER_SECOND = 5
    SCALE_DENSITY = 5
    MAX_UTIL = 100

    def __init__(self, controller, dask_address):

        self.controller = controller
        self.started = True
        self.start_time = None
        self.offset = 0
        self.last_offset = None
        self.temp_color = (['bg background', 'temp dark', 'temp light'],
                           {(1, 0): 'temp dark smooth', (2, 0): 'temp light smooth'},
                           'line')

        self.graph_data = GraphData(0, dask_address = dask_address)
        self.graph_cpu = []
        self.graph_mem = []
        self.visible_graphs = []
        self.graph_place_holder = urwid.WidgetPlaceholder(urwid.Pile([]))

        self.max_temp = None
        self.cur_temp = None
        self.top_freq = None
        self.cur_freq = None
        self.perf_lost = None

        self.main_window_w = []

        self.help_menu = HelpMenu(self.on_help_menu_close)

        urwid.WidgetPlaceholder.__init__(self, self.main_window())

    def get_offset_now(self):
        if self.start_time is None:
            return 0
        if not self.started:
            return self.offset
        tdelta = time.time() - self.start_time
        return int(self.offset + (tdelta * self.GRAPH_OFFSET_PER_SECOND))

    def update_stats(self):      
        self.n_workers_str.set_text(str(self.graph_data.n_workers))
        self.used_mem_str.set_text(str(self.graph_data.used_mem))
        self.total_mem_str.set_text(str(self.graph_data.total_mem))

    def update_graph(self, force_update=False):
        self.graph_data.graph_num_bars = self.graph_cpu.bar_graph.get_size()[1]

        o = self.get_offset_now()
        if o == self.last_offset and not force_update:
            return False
        self.last_offset = o

        self.graph_data.update_all()
        

        # Updating CPU utilization
        l = []
        for n in range(self.graph_data.graph_num_bars):
            value = self.graph_data.cpu_util[n]
            # toggle between two bar types
            if n & 1:
                l.append([0, value])
            else:
                l.append([value, 0])
        self.graph_cpu.bar_graph.set_data(l, self.graph_data.util_max_value)
        y_label_size = self.graph_cpu.bar_graph.get_size()[0]
        self.graph_cpu.set_y_label(self.get_label_scale(0, self.MAX_UTIL, y_label_size))

        # Updating Memory utilization
        l = []
        for n in range(self.graph_data.graph_num_bars):
            value = self.graph_data.mem_util[n]
            # toggle between two bar types
            if n & 1:
                l.append([0, value])
            else:
                l.append([value, 0])
        self.graph_mem.bar_graph.set_data(l, self.graph_data.mem_max_value)

        y_label_size = self.graph_mem.bar_graph.get_size()[0]
        self.graph_mem.set_y_label(self.get_label_scale(0, self.graph_data.mem_max_value, y_label_size))

        self.update_stats()

    def get_label_scale(self, min, max, size):

        if size < self.SCALE_DENSITY:
            label_cnt = 1
        else:
            label_cnt = int(size / self.SCALE_DENSITY)

        label = [int(min + i * (max - min) / label_cnt) for i in range(label_cnt + 1)]
        return label

    def toggle_animation(self):
        if self.started:  # stop animation
            self.offset = self.get_offset_now()
            self.started = False
            self.controller.stop_animation()
        else:
            self.started = True
            self.start_time = time.time()
            self.controller.animate_graph()

    def on_reset_button(self, w):
        self.offset = 0
        self.start_time = time.time()
        self.graph_data.reset()
        self.update_graph(True)

    def on_help_menu_close(self):
        self.original_widget = self.main_window_w

    def on_help_menu_open(self, w):
        self.original_widget = urwid.Overlay(self.help_menu.main_window, self.original_widget,
                                             ('fixed left', 3), self.help_menu.get_size()[1],
                                             ('fixed top', 2), self.help_menu.get_size()[0])

    def bar_graph(self, color_a, color_b, title, x_label, y_label):

        w = ScalableBarGraph(['bg background', color_a, color_b])
        bg = LabeledBarGraph([w, x_label, y_label, title])

        return bg

    def button(self, t, fn, data=None):
        w = urwid.Button(t, fn, data)
        w = urwid.AttrWrap(w, 'button normal', 'button select')
        return w

    def radio_button(self, g, l, fn):
        w = urwid.RadioButton(g, l, False, on_state_change=fn)
        w = urwid.AttrWrap(w, 'button normal', 'button select')
        return w

    def exit_program(self, w):
        raise urwid.ExitMainLoop()

    def graph_controls(self):
        self.offset = 0
        animate_controls = urwid.GridFlow([
            self.button("Reset", self.on_reset_button),
            self.button('Help', self.on_help_menu_open),
        ], 18, 2, 0, 'center')

        buttons = [
            urwid.Divider(),
            urwid.Text("Control Options", align="center"),
            animate_controls,
            urwid.Divider(),
            urwid.LineBox(urwid.Pile([
                urwid.Text("Placeholder #1", align ='left'),
                urwid.Text("Placeholder #2", align = 'left')])),
            urwid.Divider(),
            self.button("Quit", self.exit_program),
            ]

        return buttons

    def show_graphs(self):
        graph_list = []
        hline = urwid.AttrWrap(urwid.SolidFill(u'\N{LOWER ONE QUARTER BLOCK}'), 'line')

        for g in self.visible_graphs:
            if g is not None:
                graph_list.append(g)
                graph_list.append(('fixed',  1, hline))

        self.graph_place_holder.original_widget = urwid.Pile(graph_list)

    def init_overview_stats(self):
        # total mem, n workers, total threads
        self.n_workers_str = urwid.Text(str(self.graph_data.n_workers), align="right")
        self.used_mem_str  = urwid.Text(str(self.graph_data.used_mem), align="right")
        self.total_mem_str = urwid.Text(str(self.graph_data.total_mem), align="right")
        
        fixed_stats = [urwid.Divider(), urwid.Text("# Workers", align="left"),
                       self.n_workers_str] + \
                      [urwid.Divider(), urwid.Text("Used Memory", align="left"),
                       self.used_mem_str] + \
                      [urwid.Divider(), urwid.Text('Total Memory', align="left"),
                       self.total_mem_str]
        
        return fixed_stats
    
    def main_window(self):
        # Initiating the data
        self.graph_cpu = self.bar_graph('util light', 'util dark', 'CPU Utilization Across all workers[%]', [], [0, 50, 100])
        self.graph_mem = self.bar_graph('temp dark', 'temp light', 'Used Memory', [], [0, 25, 50, 75, 100])
        
        self.graph_data.graph_num_bars = self.graph_cpu.bar_graph.get_size()[1]

        self.graph_cpu.bar_graph.set_bar_width(1)
        self.graph_mem.bar_graph.set_bar_width(1)

        vline = urwid.AttrWrap(urwid.SolidFill(u'\u2502'), 'line')

        self.visible_graphs = [self.graph_cpu, self.graph_mem]
        self.show_graphs()

        graph_controls = self.graph_controls()
        overview_stats = self.init_overview_stats()

        text_col = urwid.ListBox(urwid.SimpleListWalker(overview_stats + [urwid.Divider()] + graph_controls ))

        w = urwid.Columns([('weight', 2, self.graph_place_holder),
                           ('fixed',  1, vline),
                           ('fixed',  20, text_col)],
                          dividechars=1, focus_column=2)

        self.main_window_w = w
        return self.main_window_w


class GraphController:
    """
    A class responsible for setting up the model and view and running
    the application.
    """
    def __init__(self, dask_address):
        self.loop = []
        self.animate_alarm = None
        self.view = GraphView(self, dask_address = dask_address)
        self.view.update_graph(True)

    def main(self):
        self.loop = urwid.MainLoop(self.view, self.view.palette)

        self.view.started = False  # simulate pressing to start button
        self.view.toggle_animation()

        self.loop.run()

    def animate_graph(self, loop=None, user_data=None):
        """update the graph and schedule the next update"""
        self.view.update_graph()
        self.animate_alarm = self.loop.set_alarm_in(
            UPDATE_INTERVAL, self.animate_graph)

    def stop_animation(self):
        """stop animating the graph"""
        if self.animate_alarm:
            self.loop.remove_alarm(self.animate_alarm)
        self.animate_alarm = None


def main():
    args = get_args()
    # Print version and exit
    if args.version:
        print (VERSION_MESSAGE)
        exit(0)

    # Setup logging util
    global log_file
    level = ""
    if args.debug:
        level = logging.DEBUG
        log_formatter = logging.Formatter("%(asctime)s [%(funcName)s()] [%(levelname)-5.5s]  %(message)s")
        root_logger = logging.getLogger()
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(log_formatter)
        root_logger.addHandler(file_handler)
        root_logger.setLevel(level)

    GraphController(dask_address = args.dask_address).main()


def get_args():
    parser = argparse.ArgumentParser(
        description=INTRO_MESSAGE,
        formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('-a','--address',
                            dest='dask_address',
                            action='store',
                            type=str,
                            required=True,
                            help=
                            '''
                                dask-distributed scheduler address.
                                
                                ie. 127.0.0.1:324597
                            ''')
                            
    parser.add_argument('-d', '--debug',
                        default=False, action='store_true', help="Output debug log to " + log_file)
    parser.add_argument('-v', '--version',
                        default=False, action='store_true', help="Display version")
    args = parser.parse_args()
    return args

if '__main__' == __name__:
    main()
