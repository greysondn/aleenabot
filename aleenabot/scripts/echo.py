# pretty useless script used to help me understand asyncio and test it because
# windows doesn't seem to have the traditional echo command.

def main():
    print("Loaded!")
    carryOn = True
    while carryOn:
        userInput = input("")
        if (userInput == "exit"):
            carryOn = False
        print(userInput)
    print("Exited!")

if ("__main__" == __name__):
    main()