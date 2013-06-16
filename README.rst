=================
TuneGears
=================

Written to play music from Google Music on my RaspberryPi, it's a
web frontend to mpg123 that queues any choosen song an plays
them in sequence.

Installing
==================

Make sure you have a working installation of mpg123:: 

    $ sudo apt-get install mpg123

Now to install TuneGears simply run::

    $ pip install -r requirements.txt

Start
====================

Before starting TuneGears you must change your data
inside the *config.json* file.

Then you can start tunegears with::

    $ python tunegears.py

Now connect with your favorite device, like your
smartphone to your raspberry pi on port 8080 and
you will see a list of you current Google Music
songs. Clicking any song will play it.

User interface is yet to come ;)
