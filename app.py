from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import or_
from itertools import combinations, permutations
import random
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///pool_league.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    points = db.Column(db.Integer, default=0)
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    matches_played = db.Column(db.Integer, default=0)

class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    round_number = db.Column(db.Integer, nullable=False)  # Regular rounds: 1,2,3..., Final: 999
    player1_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    player2_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    winner_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=True)
    match_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    player1 = db.relationship('Player', foreign_keys=[player1_id])
    player2 = db.relationship('Player', foreign_keys=[player2_id])
    winner = db.relationship('Player', foreign_keys=[winner_id])

class TournamentSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    num_players = db.Column(db.Integer, nullable=False)
    num_rounds = db.Column(db.Integer, nullable=False)
    win_points = db.Column(db.Integer, nullable=False)
    loss_points = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

def generate_round_matches(players):
    """
    Generate matches for a tournament where in each round:
    - Every player plays against every other player
    - For n players, each round will have n*(n-1)/2 matches
    - Each round contains all possible combinations of matches
    Returns a list of rounds, where each round contains all matches between players
    """
    n = len(players)
    
    # Generate all possible matches between players
    all_matches = []
    for i in range(n):
        for j in range(i + 1, n):
            all_matches.append((players[i], players[j]))
    
    # For the requested number of rounds, repeat all matches
    rounds = []
    round_matches = list(all_matches)  # Create a copy for each round
    rounds.append(round_matches)
    
    return rounds

def get_or_create_teams():
    teams = Player.query.all()
    if not teams:
        team_names = ['Vihar', 'Megh', 'Kirtan', 'Aryan']
        for name in team_names:
            team = Player(name=name)
            db.session.add(team)
        db.session.commit()
    return Player.query.all()

def get_player_stats(team_id):
    team = Player.query.get(team_id)
    if not team:
        return None
    
    # Get only completed matches involving this player, ordered by when they were actually played
    matches = Match.query.filter(
        or_(Match.player1_id == team_id, Match.player2_id == team_id),
        Match.winner_id.isnot(None)  # Only get matches that have been played
    ).order_by(Match.match_date.desc()).all()
    
    # Get last 5 matches results in chronological order
    recent_matches = matches[:5]
    recent_matches.reverse()  # Reverse to show oldest to newest
    last_5 = []
    
    for match in recent_matches:
        # True for win, False for loss
        last_5.append(match.winner_id == team_id)
    
    # Pad with None if less than 5 matches
    while len(last_5) < 5:
        last_5.insert(0, None)  # Add empty matches at the start
    
    # Get matches against each opponent
    opponent_stats = {}
    for match in matches:
        opponent_id = match.player2_id if match.player1_id == team_id else match.player1_id
        opponent = Player.query.get(opponent_id)
        
        if opponent.id not in opponent_stats:
            opponent_stats[opponent.id] = {
                'name': opponent.name,
                'matches': 0,
                'wins': 0,
                'losses': 0
            }
        
        opponent_stats[opponent.id]['matches'] += 1
        if match.winner_id == team_id:
            opponent_stats[opponent.id]['wins'] += 1
        else:
            opponent_stats[opponent.id]['losses'] += 1
    
    return {
        'team': team,
        'matches': matches,
        'last_5': last_5,
        'opponent_stats': opponent_stats
    }

@app.route('/')
def index():
    # Check if there's an active tournament
    active_tournament = TournamentSettings.query.filter_by(is_active=True).first()
    if active_tournament:
        session['tournament_active'] = True
        # Remove the flash message here since it's not needed
        return redirect(url_for('matches'))
    session['tournament_active'] = False
    return render_template('index.html')

@app.route('/setup_tournament', methods=['POST'])
def setup_tournament():
    try:
        # Get number of players and rounds from form
        num_players = int(request.form.get('num_players'))
        num_rounds = int(request.form.get('num_rounds'))
        win_points = int(request.form.get('win_points', 3))
        loss_points = int(request.form.get('loss_points', 0))
        
        # Get player names from indexed form fields
        player_names = []
        for i in range(1, num_players + 1):
            name = request.form.get(f'player_name_{i}')
            if name and name.strip():
                player_names.append(name.strip())
        
        # Validate player names
        if len(player_names) < 2:
            flash('Need at least 2 players for a tournament', 'error')
            return redirect(url_for('index'))
            
        # Check for unique names
        if len(set(player_names)) != len(player_names):
            flash('All player names must be unique', 'error')
            return redirect(url_for('index'))
            
        # Start database transaction
        db.session.begin_nested()
        
        # Clear any existing tournament data
        Match.query.delete()
        Player.query.delete()
        TournamentSettings.query.delete()
        
        # Create tournament settings
        settings = TournamentSettings(
            num_players=len(player_names),
            num_rounds=num_rounds,
            win_points=win_points,
            loss_points=loss_points,
            is_active=True
        )
        db.session.add(settings)
        
        # Create players
        players = []
        for name in player_names:
            player = Player(name=name)
            db.session.add(player)
            players.append(player)
        
        # Flush to get player IDs
        db.session.flush()
        
        # Generate base round structure
        base_rounds = generate_round_matches(players)
        
        # Create matches for each requested round
        for round_num in range(1, num_rounds + 1):
            # Get the base round matches (all possible combinations)
            round_matches = base_rounds[0]  # We only need the first round since all rounds are identical
            
            # Create match records for this round
            for player1, player2 in round_matches:
                match = Match(
                    player1=player1,
                    player2=player2,
                    round_number=round_num
                )
                db.session.add(match)
        
        # Commit all changes
        db.session.commit()
        
        # Set tournament as active in session
        session['tournament_active'] = True
        
        # Set a session flag to indicate this is a fresh setup
        session['fresh_setup'] = True
        
        return redirect(url_for('matches'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error setting up tournament: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/matches')
def matches():
    if not session.get('tournament_active'):
        flash('No active tournament. Please set up a tournament first.', 'warning')
        return redirect(url_for('index'))
    
    # Show setup success message only on initial setup
    if session.get('fresh_setup'):
        flash('Tournament setup complete!', 'success')
        session.pop('fresh_setup', None)  # Remove the flag after showing the message
    
    # Get all players
    players = Player.query.all()
    
    # Get tournament settings
    settings = TournamentSettings.query.first()
    
    # Get all regular round matches (excluding coin flips and finals)
    regular_matches = Match.query.filter(Match.round_number < 998).order_by(Match.round_number, Match.id).all()
    matches_by_round = {}
    
    # Convert players to JSON-serializable format
    teams = []
    for player in players:
        team_data = {
            'id': player.id,
            'name': player.name,
            'matches_played': 0,
            'wins': 0,
            'losses': 0,
            'points': 0
        }
        teams.append(team_data)
    
    # Calculate match statistics
    for match in regular_matches:
        # Add match to round grouping
        if match.round_number not in matches_by_round:
            matches_by_round[match.round_number] = []
        matches_by_round[match.round_number].append(match)
        
        # Update player statistics if match has a winner
        if match.winner_id:
            win_points = settings.win_points
            loss_points = settings.loss_points
            
            # Get both players
            player1 = next(team for team in teams if team['id'] == match.player1_id)
            player2 = next(team for team in teams if team['id'] == match.player2_id)
            
            # Update match count for both players
            player1['matches_played'] += 1
            player2['matches_played'] += 1
            
            # Update wins, losses, and points
            if match.winner_id == player1['id']:
                player1['wins'] += 1
                player1['points'] += win_points
                player2['losses'] += 1
                player2['points'] += loss_points
            else:
                player2['wins'] += 1
                player2['points'] += win_points
                player1['losses'] += 1
                player1['points'] += loss_points
    
    # Sort teams by points and wins
    teams.sort(key=lambda x: (-x['points'], -x['wins']))
    
    # Check if all regular round matches are completed
    all_rounds_complete = all(match.winner_id is not None for match in regular_matches)
    
    # Get coin flip matches
    coin_flip_matches = Match.query.filter_by(round_number=998).all()
    if coin_flip_matches:
        matches_by_round['Coin Flips'] = coin_flip_matches
    
    # Handle final match creation/update
    if all_rounds_complete:
        final_match = Match.query.filter_by(round_number=999).first()
        
        # If no final match exists and we have at least 2 players
        if not final_match and len(teams) >= 2:
            # Check if there's a tie for first or second place
            top_score = teams[0]['points']
            second_score = teams[1]['points']
            tied_for_first = sum(1 for t in teams if t['points'] == top_score) > 1
            tied_for_second = sum(1 for t in teams if t['points'] == second_score) > 1
            
            # Create final match if no ties
            if not tied_for_first and not tied_for_second:
                # Create final match between top 2 players
                final_match = Match(
                    player1_id=teams[0]['id'],
                    player2_id=teams[1]['id'],
                    round_number=999
                )
                db.session.add(final_match)
                db.session.commit()
                flash('Championship Final match has been created!', 'success')
            elif tied_for_first or tied_for_second:
                flash('There is a tie! Please use coin flip to determine finalists.', 'warning')
        
        # Add existing or newly created final match to matches_by_round
        if final_match:
            matches_by_round['Final'] = [final_match]
    
    return render_template('matches.html', teams=teams, matches_by_round=matches_by_round)

@app.route('/record_match', methods=['POST'])
def record_match():
    if not session.get('tournament_active'):
        flash('No active tournament is active.', 'error')
        return redirect(url_for('matches'))
    
    match_id = request.form.get('match_id')
    winner_id = request.form.get('winner')
    
    if not match_id or not winner_id:
        flash('Invalid match data provided.', 'error')
        return redirect(url_for('matches'))
    
    try:
        match = Match.query.get(match_id)
        if not match:
            flash('Match not found.', 'error')
            return redirect(url_for('matches'))
        
        # Get tournament settings for points
        settings = TournamentSettings.query.first()
        win_points = settings.win_points
        loss_points = settings.loss_points
        
        # If match was already recorded, reverse previous results
        if match.winner_id:
            # Get both players
            player1 = Player.query.get(match.player1_id)
            player2 = Player.query.get(match.player2_id)
            old_winner = Player.query.get(match.winner_id)
            old_loser = player1 if old_winner.id == player2.id else player2
            
            # Reverse the points and stats
            old_winner.points -= win_points
            old_winner.wins -= 1
            old_winner.matches_played -= 1
            
            old_loser.points -= loss_points
            old_loser.losses -= 1
            old_loser.matches_played -= 1
        
        # Record new result
        match.winner_id = winner_id
        
        # Get both players
        player1 = Player.query.get(match.player1_id)
        player2 = Player.query.get(match.player2_id)
        
        # Update stats for both players
        if int(winner_id) == player1.id:
            winner = player1
            loser = player2
        else:
            winner = player2
            loser = player1
        
        # Update winner stats
        winner.points += win_points
        winner.wins += 1
        winner.matches_played += 1
        
        # Update loser stats
        loser.points += loss_points
        loser.losses += 1
        loser.matches_played += 1
        
        db.session.commit()
        flash('Match result recorded successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error recording match result: {str(e)}', 'error')
    
    return redirect(url_for('matches'))

@app.route('/delete_match/<int:match_id>', methods=['POST'])
def delete_match(match_id):
    match = Match.query.get_or_404(match_id)
    
    # Update team statistics before deleting
    if match.winner_id:
        update_team_stats(match, is_delete=True)
    
    db.session.delete(match)
    db.session.commit()
    return redirect(url_for('matches'))

@app.route('/get_match/<int:match_id>')
def get_match(match_id):
    match = Match.query.get_or_404(match_id)
    return jsonify({
        'player1_id': match.player1_id,
        'player2_id': match.player2_id,
        'winner_id': match.winner_id,
        'round_number': match.round_number,
        'is_final': match.is_final
    })

@app.route('/reset_tournament', methods=['POST'])
def reset_tournament():
    try:
        # Delete all matches
        Match.query.delete()
        
        # Delete all players
        Player.query.delete()
        
        # Delete tournament settings
        TournamentSettings.query.delete()
        
        # Clear session
        session.pop('tournament_active', None)
        
        db.session.commit()
        flash('Tournament has been reset successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error resetting tournament: {str(e)}', 'error')
    
    return redirect(url_for('index'))

@app.route('/update_player_name', methods=['POST'])
def update_player_name():
    if not session.get('tournament_active'):
        flash('No active tournament.', 'error')
        return redirect(url_for('matches'))
    
    player_id = request.form.get('player_id')
    new_name = request.form.get('new_name')
    
    if not player_id or not new_name:
        flash('Invalid player data provided.', 'error')
        return redirect(url_for('matches'))
    
    try:
        player = Player.query.get(player_id)
        if not player:
            flash('Player not found.', 'error')
            return redirect(url_for('matches'))
        
        # Check if new name is unique
        existing_player = Player.query.filter(Player.name == new_name, Player.id != player_id).first()
        if existing_player:
            flash('A player with this name already exists.', 'error')
            return redirect(url_for('matches'))
        
        player.name = new_name
        db.session.commit()
        flash('Player name updated successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating player name: {str(e)}', 'error')
    
    return redirect(url_for('matches'))

@app.route('/standings')
def standings():
    if not session.get('tournament_active'):
        flash('No active tournament. Please set up a tournament first.', 'warning')
        return redirect(url_for('index'))
    
    # Get all players ordered by points and wins
    players = Player.query.order_by(Player.points.desc(), Player.wins.desc()).all()
    
    return render_template('standings.html', players=players)

@app.route('/player_stats')
def player_stats():
    if not session.get('tournament_active'):
        flash('No active tournament. Please set up a tournament first.', 'warning')
        return redirect(url_for('index'))
    
    players = Player.query.all()
    player_statistics = {}
    
    for player in players:
        stats = get_player_stats(player.id)
        if stats:
            player_statistics[player.id] = stats
    
    return render_template('player_stats.html', player_statistics=player_statistics)

@app.route('/match_history')
def match_history():
    if not session.get('tournament_active'):
        flash('No active tournament. Please set up a tournament first.', 'warning')
        return redirect(url_for('index'))
    
    # Get all matches ordered by date
    matches = Match.query.order_by(Match.match_date.desc()).all()
    
    return render_template('match_history.html', matches=matches)

@app.route('/record_coin_flip', methods=['POST'])
def record_coin_flip():
    if not session.get('tournament_active'):
        flash('No active tournament is active.', 'error')
        return redirect(url_for('matches'))
    
    winner_id = request.form.get('winner_id')
    loser_id = request.form.get('loser_id')
    
    if not winner_id or not loser_id:
        flash('Invalid coin flip data provided.', 'error')
        return redirect(url_for('matches'))
    
    try:
        # Get the players
        winner = Player.query.get(winner_id)
        loser = Player.query.get(loser_id)
        
        if not winner or not loser:
            flash('Players not found.', 'error')
            return redirect(url_for('matches'))
        
        # Check if there's an existing final match
        final_match = Match.query.filter_by(round_number=999).first()
        if final_match:
            # Update existing final match
            if winner.id not in [final_match.player1_id, final_match.player2_id]:
                # Winner replaces the loser in the final
                if final_match.player1_id == loser.id:
                    final_match.player1_id = winner.id
                else:
                    final_match.player2_id = winner.id
        else:
            # Create new final match
            final_match = Match(
                player1_id=winner.id,
                player2_id=None,  # Will be filled by next coin flip if needed
                round_number=999
            )
            db.session.add(final_match)
        
        # Record the coin flip result
        coin_flip_match = Match(
            player1_id=winner.id,
            player2_id=loser.id,
            winner_id=winner.id,
            round_number=998  # Special round number for coin flips
        )
        db.session.add(coin_flip_match)
        db.session.commit()
        
        flash(f'{winner.name} won the coin flip against {loser.name}!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error recording coin flip result: {str(e)}', 'error')
    
    return redirect(url_for('matches'))

# if __name__ == '__main__':
#     app.run(debug=True, port=5006)