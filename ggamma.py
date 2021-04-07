#!/usr/bin/env python
# GTK gamma adjustment GUI (xrandr)

import os
import re
import gi
import sys
import signal
import argparse
import configparser
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk, Gio, GdkPixbuf
from subprocess import Popen, PIPE


class GGamma:
    def __init__(self, args=[], app=None):
        self.builder = Gtk.Builder()
        self.builder.add_from_file(os.path.join(os.path.dirname(__file__), "main.ui"))
        self.builder.connect_signals(self)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self.onDestroy)

        self.window = self.builder.get_object('main-window')
        self.spec_image = self.builder.get_object('spec-image')
        self.gamma_main = self.builder.get_object('adj-gamma-main')
        #self.gamma_shift = self.builder.get_object('adj-gamma-shift')
        self.brightness = self.builder.get_object('adj-brightness')
        self.advanced = self.builder.get_object('advanced-expander')
        self.gamma_red = self.builder.get_object('adj-gamma-red')
        self.gamma_green = self.builder.get_object('adj-gamma-green')
        self.gamma_blue = self.builder.get_object('adj-gamma-blue')
        self.menu = self.builder.get_object('popover-menu')
        for scale in ['gamma-main', 'brightness', 'gamma-red', 'gamma-green', 'gamma-blue']:
            self.builder.get_object('scale-'+scale).add_mark(1, Gtk.PositionType.TOP, None)
        #self.window.set_wmclass("GGamma", "GGamma")
        if app:  self.window.set_application(app)
        default_conf = os.getenv('XDG_CONFIG_HOME', '~/.config') + '/ggamma-default.ggamma'

        # parse args
        conf_parser = argparse.ArgumentParser(add_help=False)
        #conf_parser.add_argument('--config', help=f'Configuration file location (default: {default_conf})')
        cargs, remaining_args = conf_parser.parse_known_args(args)
        parser = argparse.ArgumentParser(description='Gamma Adjustment GUI.', parents=[conf_parser])
        parser.add_argument('--gamma',         default='1', help='Set gamma in total or "R:G:B" format')
        parser.add_argument('--brightness',    type=float, default=1, help='Set brightness')
        parser.add_argument('--advanced',      action='store_true',   help='Show advnaced options')
        #parser.add_argument('--display',       help='which display to configure')
        #parser.add_argument('--save',          action='store_true', help='Save settings as defaults')
        parser.add_argument('--tray',          action='store_true',    help='Show an icon in the system tray')
        parser.add_argument('--hide',          action='store_true',    help="Don't show the window")
        parser.add_argument('--version',       action='version',      help=version, version=version)
        self.defaults = parser.parse_args([])
        self.parser = parser

        # TODO: parse config and/or parse current settings
        # parse config
        #self.cpath = os.path.expanduser(cargs.config or default_conf)
        #if os.path.exists(self.cpath):
            #copts = self.parseConfig(self.cpath)
            #parser.set_defaults(**copts)  # unfortunatly this borks the ArgumentDefaultsHelpFormatter
            #self.pargs = parser.parse_args(remaining_args)
            #print("Config:", self.cpath, copts, file=sys.stderr)  # avoid printing on help
        #else:
        self.pargs = parser.parse_args(remaining_args)
        #if cargs.config:  print('Config file not found:', self.cpath, file=sys.stderr)

        # set initial values
        self.subp = None
        #self.save = self.pargs.save
        #self.last_config_fname = 'settings.ggamma'
        #self.display = self.pargs.display
        self.resetSettings(self.pargs)
        if self.pargs.advanced:
            self.advanced.set_expanded(True)
        if not self.pargs.hide:
            self.window.show_all()
        #self.window.set_focus(self.reset_button)
        if self.pargs.tray or self.pargs.hide:
            try:
                gi.require_version('AppIndicator3', '0.1')
                from gi.repository import AppIndicator3
                self.ind = AppIndicator3.Indicator.new('ggamma', 'video-display-symbolic',
                    AppIndicator3.IndicatorCategory.APPLICATION_STATUS)
                self.ind.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
                menu = Gtk.Menu()  # Hack: indicator needs menu, but we dont want one
                menu.connect('draw', lambda a,b: (menu.hide(), self.window.present()))
                self.ind.set_menu(menu)
            except Exception as e:
                print('TRAY ERROR:', e, file=sys.stderr)

    #def parseConfig(self, cpath):
        #config = configparser.ConfigParser()
        #config.read([cpath])
        #copts = { k.replace('-', '_'): v
                  #for k, v in config.items(config.sections()[0]) }
        #if 'extras' in copts:  copts['extras'] = copts['extras'].split(' ')
        #return copts

    def resetSettings(self, pargs=None):
        if not pargs or not isinstance(pargs, argparse.Namespace):
            pargs = self.defaults  # use defaults when called by a widget
        split = pargs.gamma.split(':')
        if len(split) == 3:
            main = 1
            r,g,b = map(float, split)
        elif len(split) == 4:
            main = float(split[0])
            r,g,b = map(float, split[1:])
        else:
            main = float(split[0])
            r,g,b = 1, 1, 1
        self.gamma_main.set_value(main)
        #self.gamma_shift.set_value(pargs.gamma_shift)
        self.brightness.set_value(pargs.brightness)
        self.gamma_red.set_value(r)
        self.gamma_green.set_value(g)
        self.gamma_blue.set_value(b)
        self.needs_update = True
        self.doneAdjusting()

    def onDestroy(self, *args):
        # TODO: throws error
        Gtk.main_quit()

    def onKeyPress(self, widget, event):
        # TODO: configurable keybinds
        # play/pause on space
        if event.state & Gdk.ModifierType.CONTROL_MASK:
            # close on Ctrl+Q, etc.
            if event.keyval in [Gdk.KEY_q, Gdk.KEY_w, Gdk.KEY_c, Gdk.KEY_Q, Gdk.KEY_W, Gdk.KEY_C]:
                self.window.destroy()
            # load on Ctrl+O
            #elif event.keyval in [Gdk.KEY_o, Gdk.KEY_O]:
                #self.loadSettings()
            ## save on Ctrl+S
            #elif event.keyval in [Gdk.KEY_s, Gdk.KEY_S]:
                #self.saveSettings()

    def valueChanged(self, adj):
        # slider changed
        self.needs_update = True

    def doneAdjusting(self, widget=None, event=None):
        # resume playback with new settings
        if self.needs_update:
            self.needs_update = False
            self.set()

    def closeMenu(self, widget=None):
        self.menu.popdown()

    def saveSettings(self, widget=None):
        pass
        #filename = self.dialog('Save Settings', conf=True, save=True, filename=self.last_config_fname)
        #if not filename:  return
        #self.last_config_fname = filename
        #config = configparser.ConfigParser()
        #args = {
            #'play': self.play_button.get_active(),
            #'noise': self.noise,
            #**{ k: int(getattr(self, k).get_value())
                #for k in ['volume', 'band_center', 'band_width',
                          #'reverb', 'tremolo_speed', 'tremolo_depth'] },
            #'effects': self.pargs.effects,
            #'spectrogram': self.spec_button.get_active(),
            #'output': self.pargs.output,
            #'duration': self.duration,
            #'fade': self.fade,
            #'tray': self.pargs.tray,
            #'hide': self.pargs.hide,
            #'extras': ' '.join(self.extras or []),
        #}
        #config.read_dict({'sox-noise': {
            #k:v for k,v in args.items() if v and v != getattr(self.defaults, k) }})
        #with open(filename, 'w') as configfile:
            #config.write(configfile)

    def loadSettings(self, widget=None):
        pass
        #filename = self.dialog('Load Settings', conf=True, filename=self.last_config_fname)
        #if not filename:  return
        #self.last_config_fname = filename
        #copts = self.parseConfig(filename)
        #self.parser.set_defaults(**vars(self.defaults))
        #self.parser.set_defaults(**copts)
        #pargs = self.parser.parse_args([])
        #self.resetSettings(pargs)

    #def dialog(self, title, audio=False, conf=False, save=False, filename=None):
        ## show FileChooserDialog and return filename
        #dialog = Gtk.FileChooserDialog(title=title, parent=self.window, action=Gtk.FileChooserAction.SAVE if save else Gtk.FileChooserAction.OPEN)
        #dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE if save else Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        #if filename:
            #if filename == os.path.basename(filename):  # if filename not full path
                #dialog.set_current_name(filename)
            #else:
                #dialog.set_filename(filename)
        #if audio:
            #fltr = Gtk.FileFilter()
            #fltr.set_name('Audio files')
            #fltr.add_mime_type('audio/*')
            #dialog.add_filter(fltr)
        #if conf:
            #fltr = Gtk.FileFilter()
            #fltr.set_name('Config files')
            #fltr.add_pattern('*.sxn')
            #dialog.add_filter(fltr)
        #fltr = Gtk.FileFilter()
        #fltr.set_name('All files')
        #fltr.add_pattern('*')
        #dialog.add_filter(fltr)
        #selected = None
        #response = dialog.run()
        #if response == Gtk.ResponseType.OK:
            #selected = dialog.get_filename()
        #dialog.destroy()
        #return selected

    def set(self, button=None):
        main = self.gamma_main.get_value()
        r = self.gamma_red.get_value()   * main
        g = self.gamma_green.get_value() * main
        b = self.gamma_blue.get_value()  * main

        p = Popen(['xrandr', '--listactivemonitors'], stdout=PIPE)
        out, err = p.communicate(timeout=1)
        displays = re.findall(b'\+\*?(\w+-\d+) ', out)

        args = ['xrandr']
        for display in displays:
            args += ['--output', display.decode('utf-8'),
                '--gamma', f'{r}:{g}:{b}',
                '--brightness', str(self.brightness.get_value())]
        self.subp = Popen(args)
        print('\n ===>', ' '.join(args), file=sys.stderr)

        #p2 = Popen(['xrandr', '--current', '--verbose'], stdout=PIPE)
        #o2, e2 = p2.communicate(timeout=1)
        #gma = re.findall(b'.*Gamma:\s*(\S+)', o2)
        #brt = re.findall(b'.*Brightness:\s*(\S+)', o2)
        #print("Gamma:", gma)
        #print("Brightness:", brt)


# Integrates App with DE rich-features
class GGammaApp(Gtk.Application):
    def __init__(self, win=None):
         super().__init__(application_id='thann.ggamma')

    def run(self, args):
        # circumvent options parsing
        self.args = args[1:]
        super().run()

    def do_activate(self, args=[]):
         self.register()
         self.app = GGamma(self.args, app=self)

version = 'Unknown'
vfilename = os.path.join(os.path.dirname(__file__), '.version')
if os.path.exists(vfilename):
    # NOTE: version file is created externally by setup.py
    with open(vfilename, 'r') as ver:
        version = ver.read() or version

def start():
    sys.exit(GGammaApp().run(sys.argv))
     #GGamma(sys.argv[1:])
     #Gtk.main()

if __name__ == '__main__':
    start()
