#include <Arduino.h>
#include <Adafruit_NeoPixel.h>

/*
  PWM is available on 3,5,6,9,10,11
  
Pin D3: blacklight pwm
Pin D4: neo strip 1
Pin D6: R
Pin D8: neo strip 2
Pin D9: G
Pin D10: B
Pin D11: blacklight 2
 */


// Parameter 1 = number of pixels in strip
// Parameter 2 = pin number (most are valid)
// Parameter 3 = pixel type flags, add together as needed:
//   NEO_RGB     Pixels are wired for RGB bitstream
//   NEO_GRB     Pixels are wired for GRB bitstream
//   NEO_KHZ400  400 KHz bitstream (e.g. FLORA pixels)
//   NEO_KHZ800  800 KHz bitstream (e.g. High Density LED strip)
Adafruit_NeoPixel strip0 = Adafruit_NeoPixel(50, 4, NEO_RGB + NEO_KHZ800);
Adafruit_NeoPixel strip1 = Adafruit_NeoPixel(50, 8, NEO_RGB + NEO_KHZ800);

#define debugLed 13

void intro() {
  uint32_t red = strip0.Color(255,0,0), black = strip0.Color(0,0,0);
  for (Adafruit_NeoPixel* strip = &strip0; strip != &strip1; strip = &strip1) {
    strip->setPixelColor(0,   red); strip->show(); delay(100);
    strip->setPixelColor(0, black); strip->show(); delay(100);
    strip->setPixelColor(0,   red); strip->show(); delay(100);
    strip->setPixelColor(0, black); strip->show(); delay(100);
  }
}

void setStrip(Adafruit_NeoPixel* strip) {
  digitalWrite(debugLed, 1);
  for (uint8_t i=0; i < strip->numPixels(); i++) {
    while (Serial.available() < 3) {
    }
    byte r = Serial.read();
    byte g = Serial.read();
    byte b = Serial.read();
    strip->setPixelColor(i, strip->Color(g, r, b));
  }
  strip->show();

  digitalWrite(debugLed, 0);
}

int main(void) {
  init();
  pinMode(debugLed, OUTPUT);

    
  strip0.begin();
  strip1.begin();
  intro(); 
  Serial.begin(115200);
 
  uint8_t i;
  while (1) {
    while (Serial.available() <= 2) {
    }
    i = Serial.read();
    if (i != 0x60) {
      continue;
    }
    i = Serial.read(); // command
    if (i == 0) { // set strip: 0x60 0x00 <numPixels * 3 bytes>
      setStrip(&strip0);
    } else if (i == 1) { // strip 1
      setStrip(&strip1);
    } else if (i == 2) { // set pwm on uv1: 0x60 0x02 <level>
      while (Serial.available() < 1) {
      }
      analogWrite(3, Serial.read());
    } else if (i == 3) { // set pwm on uv2: 0x60 0x03 <level>
      while (Serial.available() < 1) {
      }
      analogWrite(11, Serial.read());
    } else if (i == 4) { // set r/g/b: 0x60 0x04 <r> <g> <b>
       while (Serial.available() < 3) {
       }
       analogWrite(6, Serial.read());
       analogWrite(9, Serial.read());
       analogWrite(10, Serial.read());
    } else {
        // unknown command
    }
  }
}
