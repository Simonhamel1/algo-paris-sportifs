#include <iostream>
#include <vector>
#include <random>
#include <cmath>
#include <iomanip>
#include <algorithm>
#include <stdexcept>

using namespace std;

// Structure pour stocker les résultats renvoyés par la fonction
struct SimulationResult {
    double final_bankroll;
    double sharpe_ratio;
    double max_drawdown;
    bool is_ruined;
    vector<double> bankroll_history;
};

SimulationResult simulate_martingale(double initial_bankroll, double base_bet, long long n_spins, double p_win) {
    double bankroll = initial_bankroll;
    double bet = base_bet;
    
    vector<double> history;
    
    // Essai d'allocation mémoire pour éviter un crash silencieux si 1 milliard de tours
    try {
        history.reserve(n_spins + 1);
    } catch (const bad_alloc& e) {
        cerr << "ERREUR : Pas assez de mémoire RAM pour stocker " << n_spins << " tours. Réduisez n_spins." << endl;
        exit(1);
    }
    
    history.push_back(bankroll);
    
    // Générateur de nombres aléatoires (Mersenne Twister), initialisé avec la seed 42
    mt19937 gen(42);
    uniform_real_distribution<> dis(0.0, 1.0);
    
    // Variables pour calculer le Max Drawdown à la volée
    double rolling_max = bankroll;
    double max_drawdown = 0.0;
    
    // Variables pour l'Algorithme de Welford (calcul de variance à la volée pour le Sharpe)
    double mean_return = 0.0;
    double M2 = 0.0;
    long long count = 0;
    
    for (long long i = 0; i < n_spins; ++i) {
        if (bankroll <= 1e-6) {
            break; // Ruine : on arrête
        }
        
        double actual_bet = min(bet, bankroll);
        double prev_bankroll = bankroll;
        
        // Le jeu
        if (dis(gen) < p_win) {
            bankroll += actual_bet;
            bet = base_bet; // Reset de la mise
        } else {
            bankroll -= actual_bet;
            bet *= 2.0; // Martingale
        }
        
        history.push_back(bankroll);
        
        // --- CALCULS À LA VOLÉE (Pour économiser la RAM) ---
        
        // 1. Max Drawdown
        if (bankroll > rolling_max) {
            rolling_max = bankroll;
        }
        double current_drawdown = (bankroll - rolling_max) / rolling_max;
        if (current_drawdown < max_drawdown) {
            max_drawdown = current_drawdown;
        }
        
        // 2. Préparation du Ratio de Sharpe (Algorithme de Welford)
        double pct_return = (bankroll - prev_bankroll) / prev_bankroll;
        count++;
        double delta = pct_return - mean_return;
        mean_return += delta / count;
        double delta2 = pct_return - mean_return;
        M2 += delta * delta2;
    }
    
    // Calcul final du Sharpe Ratio
    double sharpe_ratio = 0.0;
    if (count > 1) {
        double variance = M2 / (count - 1);
        double std_return = sqrt(variance);
        if (std_return > 0) {
            sharpe_ratio = (mean_return / std_return) * sqrt(252.0);
        }
    }
    
    bool is_ruined = (bankroll <= 1e-6);
    
    return {bankroll, sharpe_ratio, max_drawdown, is_ruined, history};
}

int main() {
    // --- PARAMÈTRES ---
    double CAPITAL_DE_DEPART = 5000000.0;
    double MISE_DE_BASE = 0.01;
    // Attention : 1 000 000 000 de tours consommera environ 8 Go de RAM.
    long long NOMBRE_DE_TOURS = 1000000000; 
    
    cout << "Simulation en cours... Cela peut prendre un peu de temps." << endl;
    
    // --- EXÉCUTION ---
    SimulationResult result = simulate_martingale(CAPITAL_DE_DEPART, MISE_DE_BASE, NOMBRE_DE_TOURS, 0.5);
    
    // --- AFFICHAGE ---
    cout << "\n--- RESULTATS DE LA SIMULATION ---" << endl;
    cout << fixed << setprecision(2); // Pour afficher les nombres avec 2 décimales
    cout << "Capital de depart : " << CAPITAL_DE_DEPART << " euros" << endl;
    cout << "Capital final     : " << result.final_bankroll << " euros" << endl;
    cout << "Tours survécus    : " << result.bankroll_history.size() - 1 << " / " << NOMBRE_DE_TOURS << endl;
    
    cout << "Banquenroute ?    : " << (result.is_ruined ? "Oui" : "Non") << endl;
    
    cout << setprecision(4); // Pour plus de précision sur les pourcentages/ratios
    cout << "Ratio de Sharpe   : " << result.sharpe_ratio << endl;
    cout << "Max Drawdown      : " << result.max_drawdown * 100.0 << " %" << endl;
    
    return 0;
}

    // g++ -O3 simulation.cpp -o simulation