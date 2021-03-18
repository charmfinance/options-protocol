from brownie import OptionViews


def main():
    source = OptionViews.get_verification_info()["flattened_source"]
    print(source)
