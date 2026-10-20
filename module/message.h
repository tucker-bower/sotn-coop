#ifndef MESSAGE_H
#define MESSAGE_H

// Shows text in the game's bottom corner text box, as soon as the game is in normal play.
// text: plain ASCII, kept alive by the caller (a string literal).
void CoopMessage(const char* text);
void CoopMessageNow(const char* text); // right away, even outside normal play (death, menus)
void MessageUpdate(void);              // per frame

#endif
