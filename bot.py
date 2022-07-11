#!/usr/bin/python3
import discord
from discord.ext import commands
from Config import config
from DB import db
from Exceptions import exceptions
import asyncio
from sys import argv

class JardinsEfemerosBot(commands.Bot):
    def __init__(self, init_file=None):
        self.options = config.read_config(init_file)
        self.prefix = self.options.get("BOT", "PREFIX")
        self.description = self.options.get("BOT", "DESCRIPTION")
        self.channels = self.options.get("BOT", "CHANNELS").split(';')
        super(JardinsEfemerosBot, self).__init__(                              
                command_prefix=self.prefix,                                     
                description=self.description                                    
                )                                                               
        self.token = self.options.get("SECRET", "TOKEN")                        
        try:                                                                    
            self.session = db.get_database(self.options)                        
        except Exception as err:                                                
            if err.args[0] == 1045:                                             
                err_text = "Access Denied"                                      
            elif err.args[0] == 2003:                                           
                err_text = "Connection Refused"                                 
            else:                                                               
                err_text = f"Error {err.args[0]}"                               
            print(err_text)                                                     
            raise err

    def run(self):
        super(JardinsEfemerosBot, self).run(self.token)

bot = JardinsEfemerosBot()

@bot.event                                                                      
async def on_ready():                                                           
    print("Logged in as:")                                                      
    print(bot.user.name)                                                        
    print(bot.user.id)                                                          
    print('-------')

async def read_messages():
    await bot.wait_until_ready()
    counter = 0
    # Fill in a filter based on last seen, eventually.
    last_message = db.get_last_message_time(bot.session())
    print(last_message)
    session = bot.session()
    while not bot.is_closed():
        for channel_id in bot.channels:
            channel = bot.get_channel(int(channel_id))
            try:
                messages = await channel.history(limit=None, after=last_message).flatten()
            except Exception as e:
                continue
            for message in messages:
                if message.created_at >= last_message:
                    last_message = message.created_at
                    db.add_message(session, message.id,
                        message.author.display_name, message.created_at,
                        message.clean_content)
        await asyncio.sleep(10)
    session.close()

async def handle_proposals():
    await bot.wait_until_ready()
    # Here we're going to look through the proposals table, find the ones that
    # are a certain amount of time from expiring, and print a reminder to vote
    # for them. We will also loop for expiring proposals, close them, and print
    # the results.
    session = bot.session()
    while not bot.is_closed():
        proposals = db.update_expiring_proposals(session)
        for channel_id in bot.channels:
            channel = bot.get_channel(int(channel_id))
        for proposal in proposals:
            await channel.send(str(proposal))
            
        await asyncio.sleep(10)
    session.close()

bot.loop.create_task(read_messages())
bot.loop.create_task(handle_proposals())

@bot.command(help="Propor uma votação para EdenX.", 
        cog="Proposta")
async def propor(ctx, number_of_days: int, proposal: str, *options):
    # Do register a proposal for others to vote on.
    try:
        session = bot.session()
        assert(type(number_of_days) == int)
        if number_of_days <= 0:
            print("ERROR: Number of days to votes must be greater than"\
                + " zero.")
            await ctx.send(f"{ctx.author.mention}: Não consegui registar a sua proposta."\
               + "O número de dias para votar deve ser superior a zero.")
            return False
        elif number_of_days > 30:
            print("ERROR: Number of days to votes must be less than"\
                + " thirty.")
            await ctx.send(f"{ctx.author.mention}: Não consegui registar a sua proposta."\
               + "O número de dias para votar deve ser inferior a 31.")
            return False
        options_str = "%;%".join(options)
        proposal = db.add_proposal(session, proposal, ctx.author.display_name, 
                options_str, number_of_days)
        if proposal is not None:
            await ctx.send(f"{ctx.author.mention} registou uma nova proposta:\n"\
                + f" {str(proposal)}")
            session.close()
            return True
        else:
            raise Exception("Proposal is None. The registration did not "\
                + "succeed.")
    except AssertionError as a:
        ctx.send("Erro: este comando esperava um número mas forneceu outra "\
            + "coisa. Um exemplo deste comando é:\n !propor 3 \"Devemos "\
            + "plantar tulipas no jardim?\" \"Sim, muitas\" \"Sim, "\
            + "algumas\" \"Não\"")
    except Exception as e:
        print(f"ERROR: Unexpected error: {str(e)}.")
        await ctx.send(f"{ctx.author.mention}: Não consegui registar a sua proposta.") 
        sesssion.close()
        return False

@bot.command(help="Votar para uma proposta.", cog="Vota")
async def votar(ctx, proposal_id: int, option: int):
    session = bot.session()
    try:
        assert(type(proposal_id) == int)
        assert(type(option) == int)

        proposal = db.get_proposal(bot.session(), proposal_id)
        if proposal is None:
            raise exceptions.ProposalDoesNotExistException()
        elif proposal.proposal_decision_status != db.ProposalStatus.popen.value:
            raise exceptions.ProposalClosedException()
        else:
            try:
                db.add_vote(session, proposal_id, option, ctx.author.display_name)
                await ctx.send(f"{ctx.author.mention}, registei com successo "\
                    + f"o seu voto para proposta {proposal_id}.")
                session.close()
                return True
            except Exception as e:
                raise e
    except AssertionError as e:
        await ctx.send("Error: Este comando está à espera de números mas " \
            + "forneceu algo diferente. Um exemplo deste comando é: \n " \
            + "!votar 1 2\nEste comando escolhe a opção 2 na proposta número 1.")
    except exceptions.DoubleVotingException as e:
        await ctx.send(f"{ctx.author.mention}, não consegui registar o seu "\
            + "voto, uma vez que já votou sobre esta proposta.")
    except exceptions.InvalidVoteException as e:
        await ctx.send(f"{ctx.author.mention}, não consegui registar o seu "\
            + "voto, uma vez que esta opção não existe.")
    except Exception as e:
        await ctx.send(f"{ctx.author.mention}, não consegui registar o seu "\
            + "voto devido a um error inesperado.")
        #print(f"ERROR: Vote failed due to {e.with_traceback()}.")
    session.close()
    return False

@bot.command(help="Mudar o seu voto numa proposta", cog="Muda")
async def mudar_voto(ctx, proposal_id: int, option: int):
    session = bot.session()
    try:
        assert(type(proposal_id)==int)
        assert(type(option)==int)
        proposal = db.get_proposal(bot.session(), proposal_id)
        if proposal is None:
            raise exceptions.ProposalDoesNotExistException()
        elif proposal.proposal_decision_status != db.ProposalStatus.popen.value:
            raise exceptions.ProposalClosedException()
        else:
            try:
                db.move_vote(session, proposal_id, option, ctx.author.display_name)
                await ctx.send(f"{ctx.author.mention}, mudei o seu voto "\
                        + f"na proposta {proposal_id} com successo.")
                session.close()
                return True
            except Exception as e:
                raise e
    except AssertionError as e:
        await ctx.send("Error: Este comando está à espera de números mas " \
            + "forneceu algo diferente. Um exemplo deste comando é: \n " \
            + "!mudar_voto 2 1\nEste comando muda o seu voto para a opção 1 "\
            + "na proposta número 1.")
    except exceptions.VoteDoesntExistException as e:
        await ctx.send(f"{ctx.author.mention}, não consegui mudar o seu "\
            + "voto, uma vez que ainda não votou sobre esta proposta.")
    except exceptions.InvalidVoteException as e:
        await ctx.send(f"{ctx.author.mention}, não consegui registar o seu "\
            + "voto, uma vez que esta opção não existe.")
    except Exception as e:
        await ctx.send(f"{ctx.author.mention}, não consegui registar o seu "\
            + "voto devido a um error inesperado.")
        #print(f"ERROR: Vote failed due to {e.with_traceback()}.")
    session.close()
    return False
        

bot.run() 
