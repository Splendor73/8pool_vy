import random
from typing import List, Dict, Tuple
from dataclasses import dataclass
from collections import defaultdict

@dataclass
class Team:
    name: str
    points: int = 0
    matches_played: int = 0
    wins: int = 0
    losses: int = 0

class LeagueCalculator:
    def __init__(self, teams: List[str]):
        self.teams = {name: Team(name=name) for name in teams}
        
    def play_match(self, team1: str, team2: str) -> Tuple[str, str, int, int]:
        """Simulate a match between two teams and return the result"""
        score1 = random.randint(0, 3)
        score2 = random.randint(0, 3)
        
        # Ensure there's always a winner (no draws)
        while score1 == score2:
            score1 = random.randint(0, 3)
            score2 = random.randint(0, 3)
        
        winner = team1 if score1 > score2 else team2
        loser = team2 if score1 > score2 else team1
        
        # Update team statistics
        self.teams[winner].points += 3
        self.teams[loser].points += 1
        self.teams[winner].wins += 1
        self.teams[loser].losses += 1
        self.teams[winner].matches_played += 1
        self.teams[loser].matches_played += 1
        
        return winner, loser, score1, score2
    
    def get_standings(self) -> List[Team]:
        """Get current league standings sorted by points"""
        return sorted(self.teams.values(), key=lambda x: (-x.points, -x.wins))
    
    def simulate_league(self):
        """Simulate entire league including both rounds"""
        team_names = list(self.teams.keys())
        
        # Simulate 2 rounds
        for round_num in range(2):
            print(f"\nRound {round_num + 1}:")
            for i in range(len(team_names)):
                for j in range(i + 1, len(team_names)):
                    team1, team2 = team_names[i], team_names[j]
                    winner, loser, score1, score2 = self.play_match(team1, team2)
                    print(f"{team1} {score1} - {score2} {team2} (Winner: {winner})")
            
            # Print standings after each round
            print("\nStandings after Round", round_num + 1)
            self.print_standings()
    
    def print_standings(self):
        """Print current league standings"""
        standings = self.get_standings()
        print("\nTeam\tPoints\tMatches\tWins\tLosses")
        print("-" * 40)
        for team in standings:
            print(f"{team.name}\t{team.points}\t{team.matches_played}\t{team.wins}\t{team.losses}")
    
    def play_final(self):
        """Play final match between top 2 teams"""
        standings = self.get_standings()
        finalist1, finalist2 = standings[0], standings[1]
        
        print(f"\nFinal Match: {finalist1.name} vs {finalist2.name}")
        score1 = random.randint(0, 3)
        score2 = random.randint(0, 3)
        
        # Ensure there's a winner in the final
        while score1 == score2:
            score1 = random.randint(0, 3)
            score2 = random.randint(0, 3)
        
        winner = finalist1.name if score1 > score2 else finalist2.name
        print(f"Final Score: {finalist1.name} {score1} - {score2} {finalist2.name}")
        print(f"League Champion: {winner}!")

def main():
    # Initialize teams
    teams = ["A", "K", "M", "V"]
    league = LeagueCalculator(teams)
    
    # Simulate league matches
    print("Starting League Simulation...")
    league.simulate_league()
    
    # Play final match
    print("\n=== FINAL MATCH ===")
    league.play_final()

if __name__ == "__main__":
    main()
