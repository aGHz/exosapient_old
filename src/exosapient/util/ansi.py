_color = "\033[1;%dm"
bold = "\033[1m"
reset = "\033[0m"

black, red, green, yellow, blue, magenta, cyan, white = [_color % i for i in range(30, 38)]

colors = {
    'black': black,
    'red': red,
    'green': green,
    'yellow': yellow,
    'blue': blue,
    'magenta': magenta,
    'cyan': cyan,
    'white': white,
    'bold': bold,
    'reset': reset,
    }
