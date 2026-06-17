// avdweb_Switch.h — desktop shim for the avdweb_Switch library. Reproduces the
// push/release/singleClick/doubleClick/longPress events (and their callbacks)
// the NI404 firmware relies on for mode switching. Backed by host button state
// (the SDL frontend), keyed by the button's pin from config.h.
#ifndef NI404_COMPAT_AVDWEB_SWITCH_H
#define NI404_COMPAT_AVDWEB_SWITCH_H

#include "config.h"
#include "ni404_host.h"

typedef void (*switchCallback_t)(void *);

class Switch {
public:
    explicit Switch(int pin, int /*pinMode*/ = 0, bool /*polarity*/ = false,
                    unsigned long /*debounce*/ = 50, unsigned long /*longPress*/ = 300,
                    unsigned long /*doubleClick*/ = 250)
        : slot(slotForPin(pin)) {}

    void poll() {
        unsigned long now = millis();
        _pushed = false;
        _released = false;
        bool level = ni404_host_button_get(slot);

        if (level && !prevLevel) {                  // rising edge = push
            _pushed = true;
            pushTime = now;
            longFired = false;
            if (pushedCb) pushedCb(pushedP);
            if (clickPending && (now - firstPushTime) <= doubleClickPeriod) {
                if (doubleCb) doubleCb(doubleP);
                clickPending = false;
                doubleConsumed = true;
            } else {
                firstPushTime = now;
                doubleConsumed = false;
            }
        }
        if (!level && prevLevel) {                  // falling edge = release
            _released = true;
            if (releasedCb) releasedCb(releasedP);
            if (!longFired && !doubleConsumed) clickPending = true;
        }
        if (level && !longFired && (now - pushTime) >= longPressPeriod) {
            longFired = true;
            clickPending = false;
            if (longCb) longCb(longP);
        }
        if (clickPending && (now - firstPushTime) > doubleClickPeriod) {
            if (singleCb) singleCb(singleP);
            clickPending = false;
        }
        prevLevel = level;
    }

    bool pushed() const { return _pushed; }
    bool released() const { return _released; }
    bool on() const { return prevLevel; }

    void setPushedCallback(switchCallback_t cb, void *p = nullptr) { pushedCb = cb; pushedP = p; }
    void setReleasedCallback(switchCallback_t cb, void *p = nullptr) { releasedCb = cb; releasedP = p; }
    void setSingleClickCallback(switchCallback_t cb, void *p = nullptr) { singleCb = cb; singleP = p; }
    void setDoubleClickCallback(switchCallback_t cb, void *p = nullptr) { doubleCb = cb; doubleP = p; }
    void setLongPressCallback(switchCallback_t cb, void *p = nullptr) { longCb = cb; longP = p; }

private:
    int slot;
    bool prevLevel = false, _pushed = false, _released = false;
    bool longFired = false, clickPending = false, doubleConsumed = false;
    unsigned long pushTime = 0, firstPushTime = 0;
    static const unsigned long longPressPeriod = 300, doubleClickPeriod = 250;

    switchCallback_t pushedCb = nullptr, releasedCb = nullptr, singleCb = nullptr,
                     doubleCb = nullptr, longCb = nullptr;
    void *pushedP = nullptr, *releasedP = nullptr, *singleP = nullptr,
         *doubleP = nullptr, *longP = nullptr;

    static int slotForPin(int pin) {
        if (pin == BTN_LEFT)   return BTN_L;
        if (pin == BTN_RIGHT)  return BTN_R;
        if (pin == BTN_MIDL)   return BTN_C;
        if (pin == BTN_MIDR)   return BTN_4;
#ifdef BTN_SW1
        if (pin == BTN_SW1)    return BTN_TOUCH1;   // PLAY
        if (pin == BTN_SW2)    return BTN_TOUCH2;   // MENU
        if (pin == BTN_SW3)    return BTN_TOUCH3;   // REC
#endif
        return BTN_4;
    }
};

#endif // NI404_COMPAT_AVDWEB_SWITCH_H
