# SSD1305 Library for driving 128x32 displays
# Might work on other sized displays, but I havn't tested them
#

#from __future__ import division
import logging
import time
from PIL import Image, ImageDraw, ImageFont


import I2C
import SPI
import GPIO

# Constants
SSD1305_I2C_ADDRESS = 0x3C    # 011110+SA0+RW - 0x3C or 0x3D

# SSD1305 commands, from datasheet
SSD1305_SETLOWCOLUMN = 0x00        # Set Low Nibble of col start addres register. [3:0]
SSD1305_SETHIGHCOLUMN = 0x10       # Set High Nibble of col start addres register. [3:0]
SSD1305_MEMORYMODE = 0x20          # Set Memory addressing Mode. Next Byte 0=Horiz, 1=Vert, 2=Page Mode
SSD1305_COLUMNADDR = 0x21          # Column Start/End Address. Two bytes follow: Start, End. 0-131
SSD1305_PAGEADDR = 0x22            # Set Start and End Pages. Two bytes follow: Start, End. 0-7
SSD1305_SETSTARTLINE = 0x40        # Set Start line of RAM. Handy for vertical scrolling screenn. [5:0]
SSD1305_SETCONTRAST = 0x81         # Set contrast. Next byte 0-255. Basically Brightness of screen
SSD1305_SETAREABRIGHTNESS = 0x82   # Set brighntess for area colour banks. Next byte 0-255
SSD1305_SETLUT = 0x91              # Set current drive pulse width of Bank0, colours A,B,C, 31-63
                                   # Bytes: Bank0, Colour A, B, C. Not tested.
SSD1305_SETBANKCOLOURPAGE0 = 0x9   # Set Bank colours of Bank1-16 (page 0). Each Bank can be 0,1,2,3 (colour A,B,C,D)
                                   # Byte 1: Bank4[7:6]  Bank3[5:4]  Bank2[3:2]  Bank1[1:0]
                                   # Byte 2: Bank8[7:6]  Bank7[5:4]  Bank6[3:2]  Bank5[1:0]
                                   # Byte 3: Bank12[7:6] Bank11[5:4] Bank10[3:2] Bank9[1:0]
                                   # Byte 4: Bank16[7:6] Bank15[5:4] Bank14[3:2] Bank13[1:0]
SSD1305_SETBANKCOLOURPAGE1 = 0x93  # The the same as above but Bank17-32 (page 1)
SSD1305_SETHORIZONTALNORMAL = 0xA0 # Segment (Horizontal) Map Normal
SSD1305_SETHORIZONTALREVERSE = 0xA1# Segment (Horizontal) Map Reversed (0->131 131->0)
SSD1305_DISPLAYALLON_RESUME = 0xA4 # Exit "All segments Lit"
SSD1305_DISPLAYALLON = 0xA5        # Display all segments on, regardless of RAM
SSD1305_NORMALDISPLAY = 0xA6       # Non-inverted Dispay mode
SSD1305_INVERTDISPLAY = 0xA7       # Inverted Display mode
SSD1305_SETMULTIPLEX = 0xA8         # Set Multiplex Ratio. Next Byte is Ratio-1. Ratios 16-64 (Set 15-63)
SSD1305_DIMSETTING = 0xAB          # Set Dim Mode Settings. Basically the Contrast and Brightness values in Dim mode
                                   # Byte 1: 0 (reserved)
                                   # Byte 2: Contrast for Bank0 (0-255)
                                   # Byte 3: Brighness for colour bank (0-255)
SSD1305_DISPLAYDIM = 0xAC          # Display On, Dim Mode
SSD1305_DISPLAYOFF = 0xAE          # Display Sleep
SSD1305_DISPLAYON = 0xAF           # Display On
SSD1305_SETSTARTPAGE = 0xB0        # Set Start Page, 0-7 [2:0]
SSD1305_COMSCANINC = 0xC0          # COM scan (Horizontal) Normal
SSD1305_COMSCANDEC = 0xC8         # COM Scam (Horizontal) Reversed (L-R) Affected by Multiplex Ratio
SSD1305_CHARGEPUMP = 0x8D          # Not Documented.
SSD1305_SETDISPLAYOFFSET = 0xD3    # Set Physical vertical shift of COM pins. Next Byte. Use 0x40 instead for scrolling
SSD1305_SETDISPLAYCLOCKDIV = 0xD5  # Display Clock Speed. Basically Refersh Rate of Display
                                   # Byte 1: Frequency Setting 0-15 [7:4] Divide Ratio 0-15 (0 is 1:1)[3:0]
SSD1305_SETCOLOURLOWPOWER = 0xD8   # Toggle Area Colour Mode and/or Low Power Display mode
                                   # Byte 1: Colour 0=Off 3=On [7:4], Power 0=Normal 5=Low [3:0]
SSD1305_SETPRECHARGE = 0xD9        # Set Pre-Charge Period for OLEDS
                                   # PreCharge 0-15 Clocks [7:4], Discharge 0-15 Clocks [3:0]
SSD1305_SETCOMPINS = 0xDA          # Com Pin (Horizontal) configuration, Sequential/Alternate and Left/Right
                                   # Byte 1: 0x02=Sequential,Normal 0x12=Alt,Norm 0x22=Seq,Reverse 0x32=Alt,Reverse
SSD1305_SETVCOMDETECT = 0xDB       # Set COMH Deselect Voltage Range (Seems a bit like traditional "contrast")
                                   # Byte 1: 0-15 [5:2] i.e Mutiply by 4. 0=0.43Vcc, 13=0.77Vcc, 15=0.83Vcc


# Scrolling constants
SSD1305_RIGHT_HORIZONTAL_SCROLL = 0x26              # Horizonal scroll setup (Right)
                                                    # Byte 1: Scroll Step 0-4 [7:0]
                                                    # Byte 2: Page Start 0-7 [7:0]
                                                    # Byte 3: Interval 0-6 [7:0]
                                                    # Byte 4: Page End 0-7 [7:0]
SSD1305_LEFT_HORIZONTAL_SCROLL = 0x27               # Same as above, but right
SSD1305_VERTICAL_AND_RIGHT_HORIZONTAL_SCROLL = 0x29 # Vertical and Right Scroll Setup
                                                    # Byte 1: Horiz Scroll Step 0-4 [7:0]
                                                    # Byte 2: Page Start 0-7 [7:0]
                                                    # Byte 3: Interval 0-6 [7:0]
                                                    # Byte 4: Page End 0-7 [7:0]
                                                    # Byte 5: Vert scroll step 1-63 (63 = 1 up) [7:0]
SSD1305_VERTICAL_AND_LEFT_HORIZONTAL_SCROLL = 0x2A  # Same as above, but Left
SSD1305_DEACTIVATE_SCROLL = 0x2E                    # Stop scrolling
SSD1305_ACTIVATE_SCROLL = 0x2F                      # Start Scrolling (only really usefull to avoid burn in?)
SSD1305_SET_VERTICAL_SCROLL_AREA = 0xA3             # Vertical Scroll Setup
                                                    # Byte 1: Number of Top rows that are fixed (above scroll area)
                                                    # Byte 2: Number of Rows to be scrolled.


class fast_ssd1305Base(object):
    """Base class for SSD1305-based OLED displays.  Implementors should subclass
    and provide an implementation for the _initialize function.
    """

    def __init__(self, width, height, rst, dc=None, sclk=None, din=None, cs=None,
                 gpio=None, spi=None, i2c_bus=None, i2c_address=SSD1305_I2C_ADDRESS,
                 i2c=None):
        self._log = logging.getLogger('fast_1305.SSD1305Base')
        self._spi = None
        self._i2c = None
        self.width = width            # Width or number of columns. Typically 128.
        self.height = height          # Height, should be a multiple of 8, as pages are 8 pix high.  Typically 32 or 64.
        self._pages = int(height / 8) # Calculare number of visible pages
        print (str(self._pages))
        self._buffer = [0]*(width*self._pages) # Buffer to store entire display before writing.
        self._pagebuffer = [0]*(width)         # Buffer to store a page before writing
        self._page = 0                         # Keep track of which page we are writing text when scrolling
        self._vert_offset = 0                  # Keep track of offset, used for manual vertical scrolling
        self._text_line = 0                    # Keep track of how many lines of text we have displayed for text scrolling
        self._pageimage = Image.new('1', (width,8)) # PIL image for page
        self._pagedraw = ImageDraw.Draw(self._pageimage) # PIL drawing canvas for page.
        # Next bits pinched from Adafruit Library
        # Default to platform GPIO if not provided.
        self._gpio = gpio
        if self._gpio is None:
            self._gpio = GPIO.get_platform_gpio()
        # Setup reset pin.
        self._rst = rst
        if not self._rst is None:
            self._gpio.setup(self._rst, GPIO.OUT)
        # Handle hardware SPI
        if spi is not None:
            self._log.debug('Using hardware SPI')
            self._spi = spi
            self._spi.set_clock_hz(8000000)
        # Handle software SPI
        elif sclk is not None and din is not None and cs is not None:
            self._log.debug('Using software SPI')
            self._spi = SPI.BitBang(self._gpio, sclk, din, None, cs)
        # Handle hardware I2C
        elif i2c is not None:
            self._log.debug('Using hardware I2C with custom I2C provider.')
            self._i2c = i2c.get_i2c_device(i2c_address)
        else:
            self._log.debug('Using hardware I2C with platform I2C provider.')
            import Adafruit_GPIO.I2C as I2C
            if i2c_bus is None:
                self._i2c = I2C.get_i2c_device(i2c_address)
            else:
                self._i2c = I2C.get_i2c_device(i2c_address, busnum=i2c_bus)
        # Initialize DC pin if using SPI.
        if self._spi is not None:
            if dc is None:
                raise ValueError('DC pin must be provided when using SPI.')
            self._dc = dc
            self._gpio.setup(self._dc, GPIO.OUT)

    def _initialize(self):
        raise NotImplementedError

    def command(self,c):
        """Send self.command byte to display."""
        if self._spi is not None:
            # SPI write.
            self._gpio.set_low(self._dc)
            self._spi.write([c])
        else:
            # I2C write.
            control = 0x00   # Co = 0, DC = 0
            self._i2c.write8(control, c)

    def data_byte(self, c):
        """Send single byte of data to display."""
        if self._spi is not None:
            # SPI write.
            self._gpio.set_high(self._dc)
            self._spi.write([c])
        else:
            # I2C write.
            control = 0x40   # Co = 0, DC = 0
            self._i2c.write8(control, c)

    def data(self, buf):
        """Send array of data to display."""
        if self._spi is not None:
            # SPI write.
            self._gpio.set_high(self._dc)
            self._spi.write(buf)
        else:
            # I2C write. TODO: This hasn't been tested at all!!
            control = 0x40   # Co = 0, DC = 0
            for c in buf:
                self._i2c.write8(control, c)

    def begin(self):
        """Initialize display."""
        # Reset and initialize display.
        self.reset()
        self._initialize()
        # Turn on the display.
        self.all_on(False)
        self.on

    def reset(self):
        """Reset the display."""
        if self._rst is None:
            return
        # Set reset high for a millisecond.
        self._gpio.set_high(self._rst)
        time.sleep(0.001)
        # Set reset low for 10 milliseconds.
        self._gpio.set_low(self._rst)
        time.sleep(0.010)
        # Set reset high again.
        self._gpio.set_high(self._rst)

    def all_on(self, all_on=True):
        if (all_on) :
            self.command(SSD1305_DISPLAYALLON)
        else :
            self.command(SSD1305_DISPLAYALLON_RESUME)

    def on(self):
        self.command(SSD1305_DISPLAYON)

    def off(self):
        self.command(SSD1305_DISPLAYOFF
                )
   # def low_power(self,low_power):
   #     self.command(SSD1305_SETCOLOURLOWPOWER)
   #     if (low_power):
   #         self.command(0x01)
   #     else :
   #         self.command(0x01)

    def invert(self,invert=True):
        if (invert):
            self.command(SSD1305_INVERTDISPLAY)
        else :
            self.command(SSD1305_NORMALDISPLAY)

    def clear(self):
        buf = [0] * (self.width) * 8

        # Configure Display
        self.command(SSD1305_MEMORYMODE)
        self.command(0x01)                    # Vertical Mode
        self.command(SSD1305_COLUMNADDR)
        self.command(0x00)                    # start Column 0
        self.command(0x7F)                    # end Column 127
        self.command(SSD1305_PAGEADDR)
        self.command(0x00)                    # start at page 0
        self.command(0x00 + 7)              # end at last page
        self.command(SSD1305_SETHORIZONTALNORMAL) # No L-R swap TODO: Needed??
        self.data(buf)

    def image(self, image):
        # Write a 1-bit PIL image to display
        # Works by Setting vertical adressing mode, and loading the image in sideways
        # So far this is the fastest python-based method to load the whole display
        if image.mode != '1':
            raise ValueError('Image must be in mode 1.')
        imwidth, imheight = image.size
        if imwidth != self.width or imheight < self.height:
            raise ValueError('Image must be same dimensions as display ({0}x{1}) (Larger Vertical Permitted).' \
                .format(self.width, self.height))
        # Rotate the image 90 degrees and Grab all the pixels from the image into a list of pixels
        # note, pixels are either 0 or 255.
        rotated=image.rotate(90,expand = True)
        pix = list(rotated.getdata())
        buf = [0] * (self.width) * self._pages

        # Configure Display
        self.command(SSD1305_MEMORYMODE)
        self.command(0x01)                    # Vertical Mode
        self.command(SSD1305_COLUMNADDR)
        self.command(0x00)                    # start Column 0
        self.command(0x7F)                    # end Column 127
        self.command(SSD1305_PAGEADDR)
        self.command(0x00)                    # start at page 0
        self.command(self._pages % 8)         # end at last page
        self.command(SSD1305_SETHORZONTALNORMAL) # No L-R swap TODO: Needed??

        # For each Page, Fill each Byte with 8 pixels
        for index in range(self.width * self._pages):
            i=(index * 8)
            buf[index] = ((pix[i] & 1)
                + (pix[i + 1] & 2)
                + (pix[i + 2] & 4)
                + (pix[i + 3] & 8)
                + (pix[i + 4] & 16)
                + (pix[i + 5] & 32)
                + (pix[i + 6] & 64)
                + (pix[i + 7] & 128))

        # Finally, write whole buffer to display
        self.data(buf)

    def page(self, image,page):
        # Write a 1-bit PIL image to page
        # Works by Setting vertical adressing mode, and loading the page in sideways
        # So far this is the fastest python-based method to load a page
        if image.mode != '1':
            raise ValueError('Image must be in mode 1.')
        imwidth, imheight = image.size
        if imwidth != self.width or imheight < 8:
            raise ValueError('Image must be same dimensions as page ({0}x{1}) (Larger Vertical Permitted).' \
                .format(self.width, 8))
        if page < 0 or page > 7:
            raise ValueError('Page must be 0-7')
        # Rotate the image 90 degrees and Grab all the pixels from the image into a list of pixels
        # note, pixels are either 0 or 255.
        rotated=image.rotate(90,expand = True)
        pix = list(rotated.getdata())
        buf = [0]*(self.width)

        # Configure Display
        self.command(SSD1305_MEMORYMODE)
        self.command(0x01)                    # Vertical Mode
        self.command(SSD1305_COLUMNADDR)
        self.command(0x00)                    # start Column 0
        self.command(0x7F)                    # end Column 127
        self.command(SSD1305_PAGEADDR)
        self.command(page % 8)                # start at page 0
        self.command(page % 8)                # end at last page
        self.command(SSD1305_SETHORIZONTALNORMAL) # No L-R swap TODO: Needed??


        for index in range(self.width):
            i=(index * 8)
            buf[index] = ((pix[i] & 1)
                + (pix[i + 1] & 2)
                + (pix[i + 2] & 4)
                + (pix[i + 3] & 8)
                + (pix[i + 4] & 16)
                + (pix[i + 5] & 32)
                + (pix[i + 6] & 64)
                + (pix[i + 7] & 128))
            index += 1
        # Finally, write whole buffer to display
        self.data(buf)

    def window(self, image, page, start, end):
        # Write a 1-bit PIL image to sub-section of a page
        # Works by Setting vertical adressing mode, and loading the page in sideways
        # So far this is the fastest python-based method to load a page
        if image.mode != '1':
            raise ValueError('Image must be in mode 1.')
        imwidth, imheight = image.size
        if imwidth != end + 1 - start or imheight < 8:
            raise ValueError('Image must be same dimensions as window ({0}x{1}) (Larger Vertical Permitted).' \
                .format(end + 1 - start, 8))
        if start < 0 or start > 127:
            raise ValueError('Window Start must be 0-127')
        if end < 0 or end > 255 or start > end:
            raise ValueError('Window End must be 0-127 and >= Start')
        if page < 0 or page > 7:
            raise ValueError('Page must be 0-7')
        # Rotate the image 90 degrees and Grab all the pixels from the image into a list of pixels
        # note, pixels are either 0 or 255.
        rotated=image.rotate(90,expand = True)
        pix = list(rotated.getdata())
        buf = [0] * (end + 1 - start)

        # Configure Display
        self.command(SSD1305_MEMORYMODE)
        self.command(0x01)                    # Vertical Mode
        self.command(SSD1305_COLUMNADDR)
        self.command((self.width - end - 1) % 128)  # start Column
        self.command((self.width - start - 1) % 128)  # end Column
        self.command(0x7F)                    # end Column 127
        self.command(SSD1305_PAGEADDR)
        self.command(page % 8)                # start at page 0
        self.command(page % 8)                # end at last page
        self.command(SSD1305_SETHORIZONTALNORMAL) # No L-R swap TODO: Needed??

        for index in range(end + 1 - start):
            #time.sleep(0.005)
            i=(index*8)
            buf[index] = ((pix[i] & 1)
                + (pix[i + 1] & 2)
                + (pix[i + 2] & 4)
                + (pix[i + 3] & 8)
                + (pix[i + 4] & 16)
                + (pix[i + 5] & 32)
                + (pix[i + 6] & 64)
                + (pix[i + 7] & 128))
        # Finally, write whole buffer to display
        self.data(buf)

    def set_contrast(self, contrast):
        """Sets the contrast of the display.  Contrast should be a value between
        0 and 255."""
        if contrast < 0 or contrast > 255:
            raise ValueError('Contrast must be a value from 0 to 255 (inclusive).')
        self.command(SSD1305_SETCONTRAST)
        self.command(contrast)

    def dim(self, dim):
        """Adjusts contrast to dim the display if dim is True, otherwise sets the
        contrast to normal brightness if dim is False.
        """
        # Assume dim display.
        contrast = 0
        # Adjust contrast based on VCC if not dimming.
        if not dim:
            if self._vccstate == SSD1305_EXTERNALVCC:
                contrast = 0x9F
            else:
                contrast = 0xCF

    def vert_offset(self, offset):
        if offset < 0 or offset > 63:
            raise ValueError('Vert Offset must be a value from 0 to 63 (inclusive).')
        self._vert_offset=offset % 64
        self.command(0x40+(self._vert_offset))

    def scroll_down(self, step):
        self._vert_offset = (self._vert_offset + step) % 64
        self.command(0x40+(self._vert_offset))

    def scroll_on(self):
        self.command(SSD1305_ACTIVATE_SCROLL)

    def scroll_off(self):
        self.command(SSD1305_DEACTIVATE_SCROLL)

    def set_vertical_scroll_area(self, start, end):
        if start < 0 or start > 63:
            raise ValueError('Scroll Area Start  must be a value from 0 to 63 (inclusive).')
        if end < 0 or end > 127:
            raise ValueError('Scroll Area End  must be a value from 0 to 127 (inclusive). ')
        self.command(SSD1305_SET_VERTICAL_SCROLL_AREA)
        self.command(start % 64)
        self.command(end % 128)

    def scroll_left(self, amount, speed):
        if amount < 0 or amount > 255:
            raise ValueError('Scroll Amount must be a value from 0 to 255 (inclusive).')
        if speed < 0 or speed > 6:
            raise ValueError('Scroll Speed must be a value from 0 to 6 (inclusive).')
        self.command(SSD1305_LEFT_HORIZONTAL_SCROLL)
        self.command(amount % 256)
        self.command(0x00) # Start Page 0
        self.command(speed % 7)
        self.command(0x03) # End Page 7
        self.scroll_on()

    def scroll_right(self, amount, speed):
        if amount < 0 or amount > 255:
            raise ValueError('Scroll Amount must be a value from 0 to 255 (inclusive).')
        if speed < 0 or speed > 6:
            raise ValueError('Scroll Speed must be a value from 0 to 6 (inclusive).')
        self.command(SSD1305_RIGHT_HORIZONTAL_SCROLL)
        self.command(amount % 256)
        self.command(0x00) # Start Page 0
        self.command(speed % 7)
        self.command(0x07) # End Page 7
        self.scroll_on()

    def scroll_vertical_right(self, h_amount, v_amount, speed):
        if h_amount < 0 or h_amount > 4:
            raise ValueError('Horzontal Scroll Amount must be a value from 0 to 4 (inclusive).')
        if v_amount < 0 or v_amount > 63:
            raise ValueError('Vertical Scroll Amount must be a value from 0 to 64 (inclusive).')
        if speed < 0 or speed > 6:
            raise ValueError('Scroll Speed must be a value from 0 to 6 (inclusive).')
        self.command(SSD1305_VERTICAL_AND_RIGHT_HORIZONTAL_SCROLL)
        self.command(h_amount % 5)
        self.command(0x01) # Start Page 0
        self.command(speed % 7)
        self.command(0x07) # End Page 7
        self.command(v_amount % 64)
        self.scroll_on()

    def scroll_vertical_left(self, h_amount, v_amount, speed):
        if h_amount < 0 or h_amount > 4:
            raise ValueError('Horzontal Scroll Amount must be a value from 0 to 4 (inclusive).')
        if v_amount < 0 or v_amount > 63:
            raise ValueError('Vertical Scroll Amount must be a value from 0 to 64 (inclusive).')
        if speed < 0 or speed > 6:
            raise ValueError('Scroll Speed must be a value from 0 to 6 (inclusive).')
        self.command(SSD1305_VERTICAL_AND_LEFT_HORIZONTAL_SCROLL)
        self.command(h_amount % 5)
        self.command(0x01) # Start Page 0
        self.command(speed % 7)
        self.command(0x07) # End Page 7
        self.command(v_amount % 64)
        self.scroll_on()

    def text_scroll(self,text,size):
        if (size == 8):
            font = ImageFont.truetype('pressstart2p.ttf',8)
            scroll = 1
        elif (size == 16):
            font = ImageFont.truetype('perfect_dos_vga_437.ttf',16)
            scroll = 2
        else:
            raise ValueError('Font size must be 8 or 16')
        max_line_length=15
        chunks = [text[i:i+max_line_length] for i in range(0, len(text), max_line_length)]
        c = 1
        indent=0
        for text in chunks:
            self._pagedraw.rectangle((0,0,self.width,8),outline=0,fill=0)
            if (c > 1):
                self._pagedraw.point([(0,6),(2,6)],fill=255)
                indent=4
            self._pagedraw.text((indent,0), text, font=font,fill=255)
            if (c < len(chunks)):
                self._pagedraw.point([(self.width-1,6),(self.width-3,6)],fill=255)
            self.page(self._pageimage,self._text_line % 8)
            if (scroll == 2) :
                self._pagedraw.rectangle((0,0,self.width,8),outline=0,fill=0)
                self._pagedraw.text((indent,-8), text, font=font,fill=255)
                self.page(self._pageimage,(self._text_line+1) % 8)
            self._text_line += scroll
            if (self._text_line > 4):
                for i in range (size):
                    self.scroll_down(1)
                    time.sleep(.05)
            c += 1

### Configuration for Waveshare 128 x 32 pixel display
class SSD1305_128_32(fast_ssd1305Base):
    def __init__(self, rst, dc=None, sclk=None, din=None, cs=None, gpio=None,
                 spi=None, i2c_bus=None, i2c_address=SSD1305_I2C_ADDRESS,
                 i2c=None):
        # Call base class constructor. Define resolution here
        super(SSD1305_128_32, self).__init__(128, 32, rst, dc, sclk, din, cs,
                                             gpio, spi, i2c_bus, i2c_address, i2c)
    def _initialize(self):
        # 128x32 pixel specific initialization.
        self.command(SSD1305_DISPLAYOFF)
        self.command(SSD1305_SETLOWCOLUMN + 4)   #--set the lower nibble of the column start addr to 4
        self.command(SSD1305_SETHIGHCOLUMN + 0)  #--set the higher nibble of the column start addr to 0
        self.command(SSD1305_SETSTARTLINE + 0)   #--set start line
        self.command(SSD1305_SETCONTRAST)
        self.command(0x80)                       # Contrast Mid
        self.command(SSD1305_SETHORIZONTALREVERSE)# Column address 131 is mapped to SEG0
        self.command(SSD1305_NORMALDISPLAY)      # Set Normal Display, not Inverse.
        self.command(SSD1305_SETMULTIPLEX)
        self.command(0x1F)                       # -- Set Multiplex --to 1/64 duty
        self.command(SSD1305_COMSCANDEC)         #--set COM Output Scan Direction to reverse
        self.command(SSD1305_SETDISPLAYOFFSET)
        self.command(0x00)                       #--set vertical shift to zero
        self.command(SSD1305_SETDISPLAYCLOCKDIV) #-set display clock divide ratio/oscillator frequency...
        self.command(0xF0)                       #..to Clock as 100 Frames/Sec (divide 0, Freg 15)
        self.command(SSD1305_SETCOLOURLOWPOWER)  #--set Area Colour mode and low power mode...
        self.command(0x05)                       #... to Monochrome, low power mode
        #self.command(0x35)                      #--Area Color mode, low power mode
        self.command(SSD1305_SETPRECHARGE)
        self.command(0xC2)                       #-- Set Pre-Charge to 15 Clocks & Discharge as 1 Clock
        self.command(SSD1305_SETCOMPINS)
        self.command(0x12)                       # Set COM pins Hardware config to alternative pin config, no COM L/R remap
        self.command(SSD1305_SETVCOMDETECT)
        self.command(0x08)                      #Set VCOM Deselect Level to 0010b
        #self.command(0x00)                       #Set VCOM Deselect Level to 0000b
        self.command(SSD1305_DISPLAYON)
