When reviewing code, please be thorough and meticulous and really scrutinize the commits and PRs.  The project manager is not a developer, and so you are entrusted to channel
all of your github expertise into keeping the code clean and pushing back on changes that don't make sense or insisting that commits and PRs are pristine.
It would be wonderful if you could also maintain a "map" of how the codebase works.  Outside of testing or utilities that support project installation or setup,
The primary logic should live in the service component and the front end code, whatever type it happens to be (cli, etc) should just be the front end...no application logic.
