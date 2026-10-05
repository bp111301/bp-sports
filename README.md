# B.P. Sports — NFL Prediction Dashboard

## Run it locally

1. Install Python 3.11+.
2. Open a terminal in this folder.
3. Install dependencies:

   pip install -r requirements.txt

4. Start the dashboard:

   streamlit run app.py

Streamlit will open the dashboard in your browser.

## Files

- app.py — dashboard
- predictions.csv — current weekly predictions
- history.csv — completed prediction history
- bp_nfl_model_v2.py — prediction/backtest engine
- requirements.txt — Python dependencies

## Updating it

Edit predictions.csv to load a weekly slate. Completed predictions can be moved
into history.csv. The next development step is connecting the model to an
automatic NFL data pipeline so these CSVs no longer need manual updates.
