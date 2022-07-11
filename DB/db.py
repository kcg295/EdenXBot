# Database imports
import sqlite3
from sqlalchemy import create_engine, Column, Integer, ForeignKey, DateTime
from sqlalchemy import String, func, desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from enum import Enum
# OS imports for paths and sys variables
import os
# Configuration file imports.
from Config import config
# Exceptions imports
from Exceptions import exceptions
# Imports for discord
from discord.ext.commands.errors import *
# Misc imports for functionality
from random import choice as randchoice
from copy import deepcopy
from datetime import datetime, date, timedelta

BASE = declarative_base()

class ProposalStatus(Enum):
    popen = 0
    psucceeded = 1
    pfailed = 2

class Message(BASE):
    __tablename__ = "messages"
    message_id = Column(Integer, primary_key=True)
    message_author = Column(String(255))
    message_content = Column(String(255))
    message_datetime = Column(DateTime) 

class Proposal(BASE):
    __tablename__ = 'proposals'
    proposal_id = Column(Integer, primary_key=True)
    proposal_author = Column(String(255))
    proposal_text = Column(String(500))
    proposal_options = Column(String(500))
    proposal_expiration= Column(DateTime)
    proposal_decision_status = Column(Integer)
    proposal_decision = Column(String(500))

    def __str__(self):
        self.proposal_expiration_string = self.proposal_expiration.strftime("%d.%m.%Y %H:%M")
        options = []
        i = 0
        for option in self.proposal_options.split('%;%'):
            i += 1
            options.append(f"{i}. {option}")
        options_string = "\n".join(options)
        return_string = f"Proposta {self.proposal_id}:\nProposta por "\
                + f"{self.proposal_author}.\n\nTexto:\n{self.proposal_text}\n\n"\
                + f"Opções:\n{options_string}\n\n"
        if self.proposal_decision_status == ProposalStatus.popen.value:
            return_string += "Proposta aberta até: "\
                    + f"{self.proposal_expiration_string}. Pode votar sobre "\
                    + f"esta proposta escrevendo !votar "\
                    + f"{self.proposal_id} opção# "\
                    + f"Por exemplo, se quisesse votar a favor da primeira "\
                    + f"opção pode escrever:\n !votar {self.proposal_id} 1"
        elif self.proposal_decision_status == ProposalStatus.psucceeded.value:
            return_string += "Proposta aprovada. Opção escholida: "\
                    + f"{str(self.proposal_decision)}."
        else:
            return_string += "Proposta falhada. Houve um empate ou não foram "\
                    + "recibidos votos."
        return return_string

class Participants(BASE):
    __tablename__ = 'participants'
    participant_id = Column(Integer, primary_key=True)
    participant_name = Column(String(255))
    participant_age = Column(Integer)
    participant_occupation = Column(String(255))
    participant_site = Column(String(255))
    participant_bio = Column(String(1024))

class Vote(BASE):
    __tablename__ = 'votes'
    vote_id = Column(Integer, primary_key=True)
    vote_author = Column(String(255))
    vote_proposal = Column(Integer, ForeignKey(Proposal.proposal_id))
    vote_choice = Column(Integer)
    
def get_database(config, create_db=False):
    file_path = config.get('DATABASE', 'FILE')
    username = config.get('DATABASE', 'USER')
    password = config.get('DATABASE', 'PASS')
    db_type = config.get('DATABASE', 'TYPE')
    db_name = config.get('DATABASE', 'NAME')
    engine = create_engine('sqlite:///'+str(file_path).strip())
    BASE.metadata.bind = engine
    if not os.path.exists(file_path):
        BASE.metadata.create_all(engine)
    DBSession = sessionmaker(bind=engine)
    return DBSession

def create_database(engine, file_path):
    try:
        BASE.metadata.bind = engine
        BASE.metadata.create_all(engine)
        DBSession = sessionmaker(bind=engine)
        return DBSession
    except Exception as e:
        raise e

def add_message(session, message_id, message_author, message_time,
                message_content):
    try:
        message = session.query(Message).filter(Message.message_id == \
                    message_id).first()
        assert message == None
        message = Message(message_id=message_id, message_author=message_author,
            message_content=message_content, message_datetime=message_time)
        session.add(message)
        session.commit()
        return True
    except AssertionError:
        return False
    except Exception as e:
        raise e

def get_last_message_time(session):
    last = session.query(Message.message_datetime,
            func.max(Message.message_datetime))
    if last.first()[0] is None:
        return datetime(2020, 1, 1, 0, 0, 0)
    else:
        return last.first()[0]

def add_vote(
                session, 
                proposal_id: int,
                vote_choice: int,
                vote_author: str
            ) -> int:
    proposal = session.query(Proposal).filter(Proposal.proposal_id == \
                    proposal_id).first()
    if proposal is None:
        raise exceptions.ProposalDoesNotExistException()
    if proposal.proposal_decision_status != ProposalStatus.popen.value:
        raise exceptions.ProposalClosedException()
    if has_voted(session, vote_author, proposal):
        raise exceptions.DoubleVotingException()
    if vote_choice <= 0 or vote_choice > len(proposal.proposal_options.split('%;%')):
        raise exceptions.InvalidVoteException()
    try:
        vote = Vote(vote_author=vote_author, vote_proposal=proposal.proposal_id,
                vote_choice=vote_choice)
        session.add(vote)
        session.commit()
        return vote.vote_id
    except Exception as e:
        # TODO: Log error.
        raise e

def move_vote(
                session, 
                proposal_id: int,
                vote_choice: int,
                vote_author: str
            ) -> int:
    proposal = session.query(Proposal).filter(Proposal.proposal_id == \
                    proposal_id).first()
    if proposal is None:
        raise exceptions.ProposalDoesNotExistException()
    if proposal.proposal_decision_status != ProposalStatus.popen.value:
        raise exceptions.ProposalClosedException()
    #if has_voted(session, vote_author, proposal):
    #    raise exceptions.DoubleVotingException()
    if vote_choice <= 0 or vote_choice > len(proposal.proposal_options.split('%;%')):
        raise exceptions.InvalidVoteException()
    try:
        vote = session.query(Vote).filter(Vote.vote_author==vote_author).filter(Vote.vote_proposal==proposal.proposal_id).first()
        if vote is None:
            raise exceptions.VoteDoesntExistException()
        vote.vote_choice = vote_choice
        session.add(vote)
        session.commit()
        return vote.vote_id
    except Exception as e:
        # TODO: Log error.
        raise e

def add_proposal(
                    session,
                    proposal_text: str,
                    proposal_author: str, 
                    proposal_choices: list,
                    proposal_days: int                
                ) -> Proposal:
    if session is None:
        raise exceptions.SessionNoneException()
    #print(proposal_choices)
    #proposal_options = "%;%".join(proposal_choices)
    proposal_expires = datetime.now() + timedelta(days=proposal_days)
    proposal = Proposal(proposal_author=proposal_author,
                        proposal_text=proposal_text,
                        proposal_options=proposal_choices,
                        proposal_expiration=proposal_expires,
                        proposal_decision_status=ProposalStatus.popen.value)
    session.add(proposal)
    session.commit()
    return proposal

def get_proposal(session, proposal_id: int) -> Proposal:
    if session is None:
        raise exceptions.SessionNoneException()
    proposal = session.query(Proposal).filter(Proposal.proposal_id == \
            proposal_id).first()
    return proposal

def get_votes(session, proposal: Proposal) -> list:
    if session is None:
        # Raise relevant exception
        raise Exception("ERROR: session is None. Please report this bug to "\
            + "Kevin Gallagher.")
    if proposal is None:
        raise exceptions.ProposalDoesNotExistException()
    try:
        votes = session.query(Vote).filter(Vote.vote_proposal==proposal).all()
        return votes
    except Exception as e:
        # TODO: Log error.
        raise e

def has_voted(session, vote_author: str, proposal: Proposal) -> bool:
    vote = session.query(Vote).filter(Vote.vote_proposal == proposal.proposal_id).filter(Vote.vote_author == vote_author).first()
    if vote is not None:
        return True
    return False

def update_expiring_proposals(session):
    proposals = session.query(Proposal).filter(Proposal.proposal_expiration <= datetime.now()).filter(Proposal.proposal_decision_status == ProposalStatus.popen.value).all()
    for proposal in proposals:
        vote_options = {}
        votes = session.query(Vote).filter(Vote.vote_proposal==proposal.proposal_id).all()
        for vote in votes:
            try:
                vote_options[vote.vote_choice] += 1
            except KeyError:
                vote_options[vote.vote_choice] = 1
        max_votes = 0
        winning_option = []
        for option in vote_options:
            if vote_options[option] > max_votes:
                max_votes = vote_options[option]
                winning_option.clear()
                winning_option.append(option)
            elif vote_options[option] == max_votes:
                winning_option.append(option)
        if len(winning_option) == 1:
            proposal.proposal_decision_status = ProposalStatus.psucceeded.value
            proposal.proposal_decision = winning_option[0]
        else:
            proposal.proposal_decision_status = ProposalStatus.pfailed.value
            proposal.proposal_decision = None
        session.commit()
    return proposals
