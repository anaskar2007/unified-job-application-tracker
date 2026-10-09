# Local OpenCATS environment

This Compose setup runs the OpenCATS application, MySQL, and phpMyAdmin alongside
the Unified Job Application Tracker. It preserves the existing port mappings:

- OpenCATS: <http://localhost:4000>
- MySQL: `localhost:3003` (containers use `opencats-db:3306`)
- phpMyAdmin: <http://localhost:8090>

## Prerequisites and image build

The OpenCATS image is built from the separate
[`tilltmk/opencats-docker`](https://github.com/tilltmk/opencats-docker) repository,
not from this project root. Its `Dockerfile` installs the PHP/Apache dependencies,
clones OpenCATS, and runs Composer. Clone it beside this repository so the
`.env.example` default path (`../opencats-docker`) resolves:

```sh
git clone https://github.com/tilltmk/opencats-docker.git ../opencats-docker
```

If you put that checkout elsewhere, set `OPENCATS_DOCKER_CONTEXT` in `.env` to its
path. Compose uses that directory as the image build context and reads its
`Dockerfile`.

The Dockerfile uses a floating `php:8.4-apache` base tag, installs current
operating-system packages, clones the current default branch of OpenCATS, and
resolves Composer dependencies at build time. This reproduces the build recipe,
but does not guarantee a bit-for-bit identical image on a later date.

## Fresh installation

1. Copy `.env.example` to `.env`.
2. Replace both password placeholders with locally chosen, strong values. Use a
   different value for the MySQL root password and the application database
   password. Do not commit `.env`.
3. Check the resolved configuration and build/start the services:

   ```sh
   docker compose config --quiet
   docker compose up -d --build
   ```

4. Check startup with `docker compose ps` and `docker compose logs -f`.
5. Complete the OpenCATS installer at <http://localhost:4000>. For its database
   connection, use host `opencats-db`, port `3306`, database `opencats`, user
   `user-here`, and the `MYSQL_PASSWORD` value from `.env`. phpMyAdmin connects
   to the same database service and user.

The named volume `opencats-docker_opencats-db-data` is for fresh installs. The
`MYSQL_DATABASE`, `MYSQL_USER`, and password variables initialize an empty MySQL
data directory; they do not change accounts or passwords in an already
initialized database.

## Existing installation and database data

The previously used data is in Docker volume
`14e2c3b8db52abd07444be75d41f0bd2b6ffeee21f9e0b716603645b98c97739`. The default
Compose configuration intentionally does **not** attach or remove that volume:
it uses a different, normal named volume for fresh installations. Do not start
Compose with the fresh-volume configuration if you intend to continue using the
existing database.

To adopt that database on the same Docker host, first make and verify a database
backup. Then, before starting Compose, change the `opencats-db-data` declaration
at the bottom of `compose.yaml` to explicitly refer to the existing volume:

```yaml
volumes:
  opencats-db-data:
    external: true
    name: 14e2c3b8db52abd07444be75d41f0bd2b6ffeee21f9e0b716603645b98c97739
```

Keep that external-volume declaration only when intentionally using this
existing volume on the host where it exists. Verify the configuration with
`docker compose config --quiet` before any startup. Back up first: Compose may replace existing
containers when it takes over, and MySQL initialization variables will not reset
or repair the existing database credentials. Use the credentials and
OpenCATS database settings that were originally configured.

To move data to another computer, a Docker volume is not transferred by this
Compose file. Make and verify a logical MySQL backup from the existing database,
then restore it into the new installation's named volume using MySQL client
tools. Do not copy a live database directory. Preserve the matching OpenCATS
database settings and credentials during the restore.

The inspected OpenCATS container has no mounted application-data volume.
Configuration created inside its writable container layer (including installer
configuration, if present) is not persisted by this Compose file and may be lost
when that container is replaced. Back it up separately before adopting Compose.
No existing containers or volumes are changed by these instructions.
