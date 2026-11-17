# Restart

```bash
make ps
make down && make up
```

Named volumes keep data. The pipeline worker re-registers the daily deployment on start.
Postgres init scripts only run on an empty volume.
