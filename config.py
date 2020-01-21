import os
TOKEN = os.getenv('TOKEN')

REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID')
REDDIT_CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET')


DEFAULT_ROLE_ID = 324786471678771200
WELCOME_Channel_ID = 324786471678771200

Owner_ID = 324786471678771200

EMBED_COLOR = 0xff171d

BOT_PREFIX = '!'
"test"
help_desc = f"""
`!help` Shows this menu
`!play` Plays a music
`!bitcoin` Shows the bitcoin price
`!say` says what you type
`!langdetect` detects what kind of language did you type
`!announce` makes an announcement in a specific Channel
`!mute` mutes the targeted user
`!kick` kicks a user from the server
`!ban` bans a user from the server
`!favmusic` plays your favorite playlist of songs
`!remind` reminds you for something important
`!time` Shows the current time (GMT+2)
`!eightball` answers your question ;3
`!serverinfo` Shows more information about the server
`!userinfo` Shows more information about a user
`!reload` reloads the bot `Developer only`
"""

eightball_random_answers = ['DO I LOOK LIKE A FORTUNE TELLER!?',
'My sources say ya... no don\'t even think about it',
'Magic 8 ball is not here right now. Please leave a message after the beep',
'You were expecting me to say yes or no, weren\'t you? Surprised you, haven\'t I?',
'Too hard to tell.',
'Rejected to Answer',
'hmm.. maybe maybe not, who knows',
'ERROR 404: Answer not found.',
'hmm.. maybe maybe not, who knows']
