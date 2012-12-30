# About "Distributed Many-in-a-row"

**School year: first master year, first semester.**

For the "Distributed Systems" course, we had to build a small project (for 25% of the grades) in teams of 3 to gain deeper understanding of group communication and coordination in distributed systems. The goal was to build a 4-in-a-row game, with the following extensions:

* variable number of players
* players don't' have to wait for their turn to make a move (!)
* the first player can choose the dimensions of the board (more than 7 columns is allowed)
* "4 in a row" doesn't have to be the endgame, the first player can choose the endgame
* players can **join and leave the game at any time**

We had to use multicast (or a simulation of it) and an absolute requirement was that every player would see the exact same board at any given time; hence moves had to be displayed on every board in the same order.  Even when there was significant network [jitter][3], our game engine had to be able to cope with this.

# Architecture

<img src="https://raw.github.com/wimleers/DistributedManyInARow/master/docs/images/DistributedGame.png" width="420" height="492" alt="Architecture" title="Architecture" />

Our implementation (visualized in the architecture schema above) first built a **layered distributed game engine**. Each layer was dumb on its own and handled one specific task. We used six layers. The schema should be mostly self-explanatory. Layer 1 was the (unreliable & unordered) messaging layer, and provided zeroconf- and IP multicast-based messaging. Layer 2 was the service layer, which would allow one to advertise a service. Layer 3 provided reliable message delivery and tracked participating hosts (including leaving & joining). Layer 4 provides a very rudimentary basis for building distributed games on top of it, through message-passing only. Layer 5 finally contained the actual game.

This layered approach allowed us to build layer upon layer, to ensure everything in the lower layers was working correctly before working on the next layer.

* [Bully algorithm][1] (to select a coordinator)
* [Zeroconf][2] (for discovery)
* Multiple games
* Player/game metadata
* Chat
* AI player

# Authors/history

If memory serves me correctly, I built the bottom four layers, [Brecht Schoolmeesters][4] and [Kristof Bamps][5] built the game logic, the AI and the GUI, and made some refinements to my work based on practical experience building the game on top of my infrastructure.

I'm sharing the code so that it's hopefully of some use to others (it was put online specifically at the request of somebody to get access to the code). I personally think the code should be cleaned up first (I first tried to implement a GlobalState/Vector clock-based approach, couldn't get that to work, so we went with an alternative, but when that was working I saw what I was doing wrong, so at the very least some clean-up can be done there) and would like to translate the report (`verslag.lyx`) from Dutch to English.

Note that **the generic core ("layered distributed game engine") of the game lives in `src/DistributedGame`**, the parts specific to many-in-a-row are in `src`.

# License

No license: public domain through [the Unlicense][6].

[1]: http://en.wikipedia.org/wiki/Bully_algorithm
[2]: http://en.wikipedia.org/wiki/Zeroconf
[3]: http://en.wikipedia.org/wiki/Jitter
[4]: http://brechtschoolmeesters.be/
[5]: #
[6]: http://unlicense.org/
