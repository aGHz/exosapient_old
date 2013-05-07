import os.path

# ./src/exosapient/apt/templates
TEMPLATE_PATH = os.path.join('.', os.path.relpath(os.path.dirname(__file__)), 'templates')

def TEMPLATE(name, data={}):
    return (os.path.join(TEMPLATE_PATH, '%s.html' % name), data)


#https://maps.google.ca/maps?saddr=3155+Chemin+de+la+C%C3%B4te+de+Liesse&daddr=33+Cote+Ste+Catherine&hl=en&ie=UTF8&sll=45.5364,-73.60091&sspn=0.017796,0.040448&dirflg=r&ttype=dep&date=13%2F05%2F02&time=17:00&noexp=0&noal=0&sort=def&mra=ls&t=m&z=15&start=0
