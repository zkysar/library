# Library Events Calendar

A static calendar displaying library events.

## Updating Events

To update the events displayed in the calendar:

1. Update the `library_data_builder.py` script to fetch new event data
2. Update the `library_events.csv` file with new event data
3. Run the data generation script:

   ```bash
   python3 generate_static_data.py
   ```

## Running Locally

To run the calendar locally, run:

```bash
python3 -m http.server
```

## Add Your API Key

To add your API key, copy the `.env.template` file and update the `AGENTQL_API_KEY` variable.