import os
import configparser

def read_config(config_file_path=None):
    if not config_file_path:
        config_file_path = os.path.join(os.getenv("HOME"), 
            ".JardinsEfemerosBot/bot.conf")
    if not os.path.exists(config_file_path):
        write_default_config(config_file_path)
    config = configparser.SafeConfigParser()
    config.read(config_file_path)
    return config

def write_default_config(config_file_path):
    if not os.path.exists(os.path.dirname(config_file_path)):
        os.makedirs(os.path.dirname(config_file_path))
    config = configparser.SafeConfigParser()
    config.add_section("SECRET")
    config.set("SECRET", "TOKEN", "<fill in with your bot token>")
    config.add_section("BOT")
    config.set("BOT", "PREFIX", "!")
    config.set("BOT", "DESCRIPTION", "A bot fo the Jardins Efemeros Project.")
    config.set("BOT", "CHANNELS", "935537937028902952")
    config.add_section("DATABASE")
    config.set("DATABASE", "TYPE", "sqlite")
    config_dir = os.path.dirname(config_file_path)
    config.set("DATABASE", "FILE", os.path.join(config_dir, 
            "sql/storage.sqlite3"))
    config.set("DATABASE", "USER", "MessageManager")
    config.set("DATABASE", "PASS", "<create a database password here>")
    config.add_section("LOG")
    config.set("LOG", "FILE", os.path.join(config_dir, "log/bot.log"))
    with open(config_file_path, 'w') as config_file:
        config.write(config_file)
    print(f"Config file {config_file_path} written! Please modify the " \
            "config file and re-run the program!")
    exit(0)
