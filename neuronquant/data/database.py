#!/usr/bin/env python
#
# Copyright 2012 Xavier Bruhiere
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import csv
from datetime import date, timedelta
from models import Base, Symbol, Quote, Metrics, Performances
#, Indicator
from numpy import array
#, asarray
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker
#, joinedload
from sqlalchemy.sql import and_

#import indicators
import os
import json
import yahoofinance as quotes

import plac
import logbook
log = logbook.Logger('Database')


class Database(object):

    def __init__(self):
        """
        Set up database access
        """
        self.Base = Base

        # Handle edge case here
        sql = json.load(open('/'.join((os.environ['QTRADE'], 'config/mysql.cfg')), 'r'))
        if sql['PASSWORD'] == '':
            engine_config = 'mysql://%s@%s/%s' % (sql['USER'],
                                                  sql['HOSTNAME'],
                                                  sql['DATABASE'])
        else:
            engine_config = 'mysql://%s:%s@%s/%s' % (sql['USER'],
                                                     sql['PASSWORD'],
                                                     sql['HOSTNAME'],
                                                     sql['DATABASE'])
        self.Engine = create_engine(engine_config)
        self.Session = sessionmaker()
        self.Session.configure(bind=self.Engine)


class Manager(object):
    """ Stock Database Manager
    This is used to manage the stock database
    """
    #TODO Split tables per index

    def __init__(self):
        self.db = Database()

    def create_database(self):
        '''
        Create stock database tables if they do not exist already
        '''
        self.db.Base.metadata.create_all(self.db.Engine)

    #TODO Error handler if the symbol does not exist
    def add_stock(self, ticker, name=None, exchange=None,
                  sector=None, industry=None):
        """ Add a stock to the stock database
        Add the stock to the symbols table and populate quotes table with all
        available historical quotes. If any of the optional parameters are left
        out, the corresponding information will be obtained from Yahoo!
        Finance.
        :param ticker: Stock ticker symbol
        :param name: (optional) Company/security name
        :param exchange: (optional) Exchange on which the security is traded
        :param sector: (optional) Company/security sector
        :param Industry (optional) Company/security industry
        """
        ticker = ticker.lower()
        session = self.db.Session()

        if self.check_stock_exists(ticker, session):
            log.warn("Stock {} already exists!".format((ticker.upper())))
            return

        #TODO Add start and end date in it, and store after downloads
        #TODO Plenty of checks
        if name is None:
            name = quotes.get_name(ticker)
        if exchange is None:
            exchange = quotes.get_stock_exchange(ticker)
        if sector is None:
            sector = quotes.get_sector(ticker)
        if industry is None:
            industry = quotes.get_industry(ticker)

        stock = Symbol(ticker, name, exchange, sector, industry)
        session.add(stock)

        q = self._download_quotes(ticker, date(1960, 01, 01), date.today())
        #for quote in q:
            #quote.Features = Indicator(quote.Id)
        session.add_all(q)
        session.commit()
        session.close()
        self.update_quotes(ticker)

    def _download_quotes(self, ticker, start_date, end_date):
        """ Get quotes from Yahoo Finance
        """
        ticker = ticker.lower()
        if start_date == end_date:
            return
        start = start_date
        end = end_date
        data = quotes.get_historical_prices(ticker, start, end)
        data = data[len(data) - 1:0:-1]
        if len(data):
            return [Quote(ticker, val[0], val[1], val[2],
                          val[3], val[4], val[5], val[6])
                    for val in data if len(val) > 6]
        else:
            return

    #def _calculate_indicators(self, ticker):
        #""" Calculate indicators and add to indicators table
        #"""
        #ticker = ticker.lower()
        #session = self.db.Session()
        #data = asarray(zip(*[(int(quote.Id), quote.AdjClose)
                             #for quote in session.query(Quote)
                             #.filter_by(Ticker=ticker)
                             #.order_by(Quote.Date).all()]))
        #for ind in indicators.calculate_all(data):
            #if not self.check_indicator_exists(ind.Id, session):
                #session.add(ind)
        #session.commit()
        #session.close()

    def update_quotes(self, ticker, check_all=True):
        """
        Get all missing quotes through current day for the given stock
        """
        #TODO Update end (start ?) date in Symbol
        ticker = ticker.lower()
        stockquotes = None
        session = self.db.Session()
        last = session.query(Quote).filter_by(
            Ticker=ticker).order_by(desc(Quote.Date)).first().Date
        start_date = last + timedelta(days=1)
        end_date = date.today()
        if end_date > start_date:
            stockquotes = self._download_quotes(ticker, start_date, end_date)
            if stockquotes is not None:
                #for quote in stockquotes:
                    #quote.Features = Indicator(quote.Id)
                session.add_all(stockquotes)
        #indicators.update_all(ticker, session, False, check_all)
        session.commit()
        session.close()

    def sync_quotes(self, check_all=False):
        """
        Updates quotes for all stocks through current day.
        """
        for symbol in self._stocks():
            self.update_quotes(symbol, check_all)
            log.info('Updated quotes for {}'.format(symbol))

    def check_stock_exists(self, ticker, session=None):
        """
        Return true if stock is already in database
        """
        newsession = False
        if session is None:
            newsession = True
            session = self.db.Session()
        exists = bool(
            session.query(Symbol).filter_by(Ticker=ticker.lower()).count())
        if newsession:
            session.close()
        return exists

    def check_quote_exists(self, ticker, q_date, session=None):
        """
        Return true if a quote for the given symbol and date exists in the
        database
        """
        newsession = False
        if session is None:
            newsession = True
            session = self.db.Session()
        exists = bool(session.query(Symbol).filter_by(Ticker=ticker.lower(),
                                                      Date=q_date).count())
        if newsession:
            session.close()
        return exists

    #def check_indicator_exists(self, qid, session=None):
        #""" Return True if indicator is already in database
        #"""
        #newsession = False
        #if session is None:
            #newsession = True
            #session = self.db.Session()
        #exists = bool(session.query(Indicator).filter_by(Id=qid).count())
        #if newsession:
            #session.close()
        #return exists

    #NOTE Redundant with available_stocks ?
    def _stocks(self, session=None):
        newsession = False
        if session is None:
            newsession = True
            session = self.db.Session()
        stocks = array([stock.Ticker for stock in session.query(Symbol).all()])
        if newsession:
            session.close()
        return stocks

    def add_stock_from_file(self, file_path):
        with open(file_path, 'rb') as index_file:
            reader = csv.reader(index_file)
            for symbol in reader:
                log.info('Add symbol {} to database'.format(symbol[0]))
                try:
                    self.add_stock(symbol[0])
                except:
                    log.error('** Error: Could not add {} symbol'.format(symbol[0]))


class Client(object):
    """ Stock database client
    The stock database client is used to access the stock database.
    """

    #NOTE Each time open and close session ?
    def __init__(self):
        self.db = Database()
        self.manager = Manager()

    def save_metrics(self, dataframe):
        """
        """
        session = self.db.Session()
        #TODO Id and other politics to define
        session.execute("delete from Metrics where Name = '{}'".format(dataframe['Name'][0]))
        #NOTE This function is not generic AT ALL
        metrics_object = [Metrics(dataframe['Name'][i], dataframe['Period'][i], dataframe['Sharpe.Ratio'][i],
                                  dataframe['Returns'][i], dataframe['Max.Drawdown'][i], dataframe['Volatility'][i],
                                  dataframe['Beta'][i], dataframe['Alpha'][i], dataframe['Excess.Returns'][i],
                                  dataframe['Benchmark.Returns'][i], dataframe['Benchmark.Volatility'][i],
                                  dataframe['Treasury.Returns'][i])
                    for i in range(len(dataframe.index))]
        session.add_all(metrics_object)
        session.commit()
        session.close()

    def save_performances(self, dataframe):
        """
        """
        session = self.db.Session()
        #TODO Id and other politics to define
        session.execute("delete from Performances where Name = '{}'".format(dataframe['Name']))
        #NOTE This function is not generic AT ALL
        perfs_object = Performances(dataframe['Name'], dataframe['Sharpe.Ratio'], dataframe['Returns'],
                                  dataframe['Max.Drawdown'], dataframe['Volatility'], dataframe['Beta'],
                                  dataframe['Alpha'], dataframe['Benchmark.Returns'])
        session.add(perfs_object)
        session.commit()
        session.close()

    def get_quotes(self, ticker, date=None, start_date=None, end_date=None, dl=False):
        """
        Return a list of quotes between the start date and (optional) end date.
        if no end date is specified, return a list containing the quote for the
        start date.
        :param ticker: Stock ticker symbol
        :param start_date:  Starting date for quotes to retrieve, str format(2012-12-01) or datetime.date[time]
        :param end_date: (optional) if more than one quote is desired, the
         ending date for the list of quotes.
        :param date: Retrieve a quote only at this date

        Access: stockquotes[x].Close
        """
        #TODO get ticker symbol from ticker
        #TODO Multiple tickers, make a panel, in an upper function
        ticker = ticker.lower()
        session = self.db.Session()
        if not self.manager.check_stock_exists(ticker, session):
            if dl:
                log.notice('Stock {} not available in database, downloading it.'.format(ticker))
                self.manager.add_stock(ticker)
                session.commit()
            else:
                log.warn('Stock {} not available in database and download forbidden'.format(ticker))
                return None

        if date is not None:
            query = session.query(Quote).filter(and_(Quote.Ticker == ticker,
                                                     Quote.Date == date)).all()
        elif start_date is not None:
            if end_date is not None:
                query = session.query(Quote).filter(and_(Quote.Ticker == ticker,
                                                         Quote.Date >= start_date,
                                                         Quote.Date <= end_date))\
                    .order_by(Quote.Date).all()
            else:
                query = session.query(Quote).filter(and_(Quote.Ticker == ticker,
                                                         Quote.Date >= start_date)).all()
        else:
            query = session.query(Quote).filter(and_(Quote.Ticker == ticker)).all()

        session.close()
        #TODO Make it a pandas dataframe
        return query

    def get_infos(self, **kwargs):
        #TODO Here too a dataframe
        name = kwargs.get('name', None)
        symbol = kwargs.get('symbol', None)
        session = self.db.Session()
        if name is not None:
            #asset = session.query(Symbol).get(asset.Ticker)
            asset = session.query(Symbol).filter(Symbol.Name == name).first()
        elif symbol is not None:
            asset = session.query(Symbol).filter(Symbol.Ticker == symbol).first()
        else:
            log.error('** Error: No suitable information provided.')
            session.close()
            return None
        if not asset:
            log.error('** Error: Could not retrieve informations')
            return None
        if asset not in session:
            asset = session.query(Symbol).get(asset.Ticker)
        #NOTE This prints ensure the assetQuotes persistence
        log.info('Got infos: {}'.format(asset))
        #print('Got associated quotes: {}'.format(asset.Quotes[0]))
        session.close()
        return asset

    def available_stocks(self, key='name'):
        ''' Return a list of the stocks available in the database '''
        session = self.db.Session()
        if key == 'symbol':
            stocks = array([stock.Ticker for stock in session.query(Symbol).all()])
        elif key == 'name':
            stocks = [stock.Name for stock in session.query(Symbol).all()]
        else:
            raise NotImplementedError()
        session.close()
        return stocks


@plac.annotations(
    symbols=plac.Annotation("Add provided stocks to db", 'option', 'a'),
    sync=plac.Annotation("Update quotes stored in db", 'flag', 's'),
    create=plac.Annotation("Create database from written models", 'flag', 'c'))
def main(sync, create, symbols=None):
    ''' MySQL Stocks database manager '''
    db = Manager()

    if create:
        db.create_database()

    if sync:
        db.sync_quotes()

    else:
        assert symbols
        if symbols.find('csv') > 0:
            db.add_stock_from_file(symbols)
        elif symbols.find(',') > 0:
            stocks = symbols.split(',')
            for ticker in stocks:
                db.add_stock(ticker)
        else:
            db.add_stock(symbols)


if __name__ == '__main__':
        plac.call(main)
