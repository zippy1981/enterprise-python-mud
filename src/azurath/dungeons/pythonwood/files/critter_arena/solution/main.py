"""The front door of critter-quest: run me with `python main.py`!"""

from critters.battle import winner


def main():
    sparky = {"name": "Sparky", "health": 30, "power": 12}
    mossy = {"name": "Mossy", "health": 40, "power": 7}
    print(f"{sparky['name']} vs {mossy['name']}!")
    champion = winner(sparky, mossy)
    if champion == "draw":
        print("It's a draw!")
    else:
        print(f"{champion} wins!")


if __name__ == "__main__":
    main()
