// emu_irq.h — the emulator's "interrupt" model.
//
// On the Teensy, three things run outside loop(): IntervalTimer ISRs (TŒRN's sequencer
// playNote, the MIDI clock, fills), the audio library's update (a low-priority software
// IRQ) and USB. The firmware protects shared state with noInterrupts()/interrupts() and
// AudioNoInterrupts()/AudioInterrupts().
//
// Here every one of those "interrupt contexts" runs on its own host thread (timer thread,
// SDL audio callback) while holding ONE recursive lock, and the firmware's critical
// sections take the same lock. One lock means no lock-order deadlocks, and loop() is
// never preempted inside a noInterrupts() section, as on the hardware.
#ifndef NI404_COMPAT_EMU_IRQ_H
#define NI404_COMPAT_EMU_IRQ_H

#include <mutex>

std::recursive_mutex &ni404_irq_lock();

#endif // NI404_COMPAT_EMU_IRQ_H
