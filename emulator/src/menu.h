// menu.h — in-window settings/config overlay for the emulator: audio output/input
// device selection, master volume, MIDI device + mapping info, and the key legend.
// Toggle with TAB. Owns the SDL audio device (opens/reopens on selection).
#ifndef NI404_MENU_H
#define NI404_MENU_H

#include <SDL.h>

// Open the audio device per saved settings; cb is the audio render callback.
void menu_init(SDL_AudioCallback cb);
void menu_shutdown();

// Handle an SDL event. Returns true if the menu consumed it (so the caller should
// NOT forward the key to the firmware/emulator).
bool menu_handle_event(const SDL_Event &e);

bool menu_is_open();

// Draw the overlay (only renders when open) plus any active toast notification.
void menu_render(SDL_Renderer *ren, int winW, int winH);

// Show a transient notification banner at the top of the window (e.g. the result
// of a drag-and-drop sample import). Drawn by menu_render for a few seconds.
void menu_toast(const char *msg);

#endif // NI404_MENU_H
