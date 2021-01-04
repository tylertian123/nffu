# Deploying NFFU

NFFU uses Docker for deployment. If you aren't familiar with Docker, we recommend you do some Googling and both familiarize yourself with it and set it up on whatever server/machine you plan to run NFFU on.

There are 3 main steps to getting NFFU up and running. These are:

- Building the containers
- Generating an encryption key
- Initializing the database

## Building the containers

This is a fairly standard procedure. All you need to do is run `docker-compose build` at the root of this repository. You may find that enabling Buildkit speeds up the builds considerably (set environment variables
`DOCKER_BUILDKIT` and `COMPOSE_DOCKER_CLI_BUILD` to 1).

If you're deploying to a swarm, you probably will want to adjust the registry in the compose file to something other than our private one. There are currently no plans to push the images to Docker Hub or any similar service.

Once you've done this, you can continue on to generating an encryption key.

If you want to customize parts of the build, see the end of the guide for more advanced tweaks you can perform.

## Generating an encryption key

NFFU tries to protect users' TDSB credentials by encrypting them with a key. Because we need to login as the user to both get their timetable and (in most cases) fill in the form, we do need to be able to retrieve
their password and student number on-demand. 

To set up the encryption key, get 32 bytes of crypto-quality randomness and place them in a file. On \*nix-y systems you can usually do this with something like

```
$ dd if=/dev/urandom bs=1 count=32 of=lockbox-credential-key
```

If you're deploying to a swarm, you should import this file as a secret, modify the compose file to set the secret as "external", and then use `docker stack deploy` to set up NFFU as a stack on the swarm. If you want to run it locally, 
you can leave the file named like that and just do a normal `docker-compose up -d`. You may need to change additional settings to get it to survive a host reboot.

You may also find it prudent to make sure the exposed port for web access is compatible with your network setup, the default is `8083`. NFFU isn't setup for HTTPS and was primarily designed to run behind some form of reverse proxy 
for TLS.

## Initializing the database

Once the containers are started, you should get a shell into the `fenetre` container (if you're running locally this can usually be accomplished with `docker exec -it nffu_fenetre_1 /bin/bash`) and run the `quart init-auth` command.
This will prompt you for a username and password to create an initial administrator account.

After doing that, you should be able to log in and set up the rest of NFFU in a web browser normally.

## Gotchas

### NFFU only works if used in one school only

The biggest problem you might encounter with NFFU is that it's only designed to work for one school per instance. This is because the only thing that uniquely
identifies a course in NFFU is its course code; so if you try to use NFFU with students from multiple schools there _will_ be conflicts (there are also some
additional internal assumptions based on this, like that if there isn't school on a given day for one student all other students can have form-filling delayed
to save some CPU and network).

If you wish to prevent students from other schools from using the system, you can set the `LOCKBOX_SCHOOL` environment variable for lockbox to the code of
the school `nffu` is intended for. If this env var is set, `nffu` will block out students from other schools when TDSB credentials are first entered.

## FAQ

TODO

## Advanced Tweaks

### Environment Variables

There are some env vars that you can set for lockbox to change some settings such as the time it submits forms and does day checks, or disable form submission
altogether. For the most up-to-date list, see the docstring for `/lockbox/lockbox/__init__.py`.

### Adjusting the Disclaimers

You might want to add additional terms to the Disclaimers page that all users are required to acknowledge. You can add whatever additional components you want by modifying the `fenetre/websrc/signup_wizard/sign_eula.js` file. Make sure
you rebuild (and potentially redeploy) at least the `fenetre` container after doing this.
