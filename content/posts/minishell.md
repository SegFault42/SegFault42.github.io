---
title: "Ecriture d'un shell"
date: '2018-10-12'
layout: 'portfolio'
featured: true
---

Un shell est la couche la plus haut niveau du systeme Unix.

Pour faire simple, un shell est un programme qui prend en input une commande, la parse et l'execute.

Nous allons diviser le travaille en plusieurs partie :

- Recuperer en boucle l'entree de l'utilisateur
- Parser l'entree utilisateur
- Executer la commande
- Coder les builtin
- Gestion de l'environement

Tout au long de ce tutorial, la compilation ce fera comme suit :

	clang -Weverything -fsanitize=address minishell.c -o minishell

## 1) Boucle principale

On commence par faire une boucle dans laquelle on lit STDIN (la commande de l'user)

```
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

int	main()
{
	char	*buffer = NULL;
	size_t	buf_size = 2048;

	// alloc buffer qui stockera la commande entree par l'user
	buffer = (char *)calloc(sizeof(char), buf_size);
	if (buffer == NULL) {
		perror("Malloc failure");
		return (EXIT_FAILURE);
	}

	// ecriture d'un prompt
	write(1, "$> ", 3);

	// lecture de STDIN en boucle
	while (getline(&buffer, &buf_size, stdin) > 0) {
		printf("cmd = %s\n", buffer);
		write(1, "$> ", 3);
	}

	printf("Bye \n");
	free(buffer);
}
```

Nous avons un programme qui affiche un prompt et qui stock l'entree de l'utilisateur en boucle. On envoie EOF (Ctrl+D au shell pour quitter)

Output :

	$> ls -la
	cmd = ls -la
	
	$> cd ~/
	cmd = cd ~/
	
	$> pwd
	cmd = pwd
	
	$> Bye 

Il faut maintenant faire une fonction qui parse la commande.

## 2) Parsing

Prenons pour exemple la commande :

	ls -la /

Nous avons le nom du binaire (ls) et ses arguments.

la commande pourrais aussi etre :

	$>  ls       -la      /  

Nous allons ecrire une fonction qui va stocker notre commande (sans les espaces) dans un char **
Ce qui donnera :

	[ls][-la][/]

```
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>

static char	**split(char *raw_cmd, char *limit)
{
	char	*ptr = NULL;
	char	**cmd = NULL;
	size_t	idx = 0;

	// split sur les espaces
	ptr = strtok(raw_cmd, limit);

	while (ptr) {
		cmd = (char **)realloc(cmd, ((idx + 1) * sizeof(char *)));
		cmd[idx] = strdup(ptr);
		ptr = strtok(NULL, limit);
		++idx;
	}
	// On alloue un element qu'on met a NULL a la fin du tableau
	cmd = (char **)realloc(cmd, ((idx + 1) * sizeof(char *)));
	cmd[idx] = NULL;
	return (cmd);
}

static void	free_array(char **array)
{
	for (int i = 0; array[i]; i++) {
		free(array[i]);
		array[i] = NULL;
	}
	free(array);
	array = NULL;
}
```

Comme on alloue dynamiquement notre `char **`, on fait une fonction (free_array) qui va liberer notre allocation.

Nous sommes maintenant pret a executer notre commande avec `execve`

## 3) Execution

Pour executer notre commande nous allons utiliser le syscall `execve`.

Nous devons utiliser le syscall `fork` pour cree un nouveau processus et lancer notre commande dans ce dernier.

Ce qui donne ca :

```
static void	exec_cmd(char **cmd)
{
	pid_t	pid = 0;
	int		status = 0;

	// On fork
	pid = fork();
	if (pid == -1)
		perror("fork");
	// Si le fork a reussit, le processus pere attend l'enfant (process fork)
	else if (pid > 0) {
		// On block le processus parent jusqu'a ce que l'enfant termine puis
		// on kill le processus enfant
		waitpid(pid, &status, 0);
		kill(pid, SIGTERM);
	} else {
		// Le processus enfant execute la commande ou exit si execve echoue
		if (execve(cmd[0], cmd, NULL) == -1)
			perror("shell");
		exit(EXIT_FAILURE);
	}
}
```

Si on compile est on execute le code, voila ce qu'il ce passe :

	$> ls
	shell: No such file or directory
	$> /bin/ls
	README.md  main.c  mainn.c  minishell
	$> Bye 


En envoyant une commande simple comme `ls` a notre shell, `execve` nous renvoie -1 et `perror` affiche `No such file or directory`.

Le premier argument de `execve` doit etre le chemin absolue du binaire a executer.

Pour lancer une commande sans donner le chemin absolue, nous devons chercher ou ce trouve le binaire `ls`, concatener le path + le nom du binaire et enfin le passer en premier argument a `execve`

Pour trouver ou ce trouve un programe, nous devons utiliser  la variable d'environnement `PATH`. Si on execute la commande :

	$> echo $PATH

Nous allons avoir un output qui ressemble a celui la :

	/bin:/usr/bin:/usr/local/bin

Il sagit des dossiers (separer par ':') ou notre shell va chercher notre binaire a executer.

Nous devons maintenant ecrire la fonction qui va concatener notre path et le binaire.

Il faut recuperer le contenu de la variable $PATH avec la fonction `getenv`. Elle prend un seul parametre qui est la variable que l'on cherche et renvoie un pointeur sur le contenue de la variable passer en parametre.

Si notre binaire n'est dans aucun dossier, on peut avertir l'utilisateur par un `Command not found`, sinon on peut executer notre execve :D.

La fonction qui recupere le recuperere la contenue de la variable $PATH et qui renvoie le chemin absolue :

```
static void	get_absolute_path(char **cmd)
{
	char	*path = strdup(getenv("PATH"));
	char	*bin = NULL;
	char	**path_split = NULL;

	if (path == NULL) // si le path est null, on cree un path
		path = strdup("/bin:/usr/local/bin:/usr/bin:/bin:/usr/local/sbin");

	// si cmd n'est pas le chemin absolue, on cherche le chemin absolue du
	// binaire grace a la variable d'environement PATH
	if (cmd[0][0] != '/' && strncmp(cmd[0], "./", 2) != 0) {

		// On split le path pour verifier ou ce trouve le binaire
		path_split = split(path, ":");
		free(path);
		path = NULL;

		// On boucle sur chaque dossier du path pour trouver l'emplacement du binaire
		for (int i = 0; path_split[i]; i++) {
			// alloc len du path + '/' + len du binaire + 1 pour le '\0'
			bin = (char *)calloc(sizeof(char), (strlen(path_split[i]) + 1 + strlen(cmd[0]) + 1));
			if (bin == NULL)
				break ;

			// On concat le path , le '/' et le nom du binaire
			strcat(bin, path_split[i]);
			strcat(bin, "/");
			strcat(bin, cmd[0]);

			// On verfie l'existence du fichier et on quitte la boucle si access
			// renvoi 0
			if (access(bin, F_OK) == 0)
				break ;

			// Nous sommes des gens propre :D
			free(bin);
			bin = NULL;
		}
		free_array(path_split);

		// On remplace le binaire par le path absolue ou NULL si le binaire
		// n'existe pas
		free(cmd[0]);
		cmd[0] = bin;
	} else {
		free(path);
		path = NULL;
	}
}
```

Notre main devient :

```
int	main()
{
	char	*buffer = NULL;
	size_t	buf_size = 2048;

	// alloc buffer qui stockera la commande entree par l'user
	buffer = (char *)calloc(sizeof(char), buf_size);
	if (buffer == NULL) {
		perror("Malloc failure");
		return (EXIT_FAILURE);
	}

	// ecriture d'un prompt
	write(1, "$> ", 3);

	// lecture de STDIN en boucle
	while (getline(&buffer, &buf_size, stdin) > 0) {
		cmd = split(buffer, " \n\t");
		get_absolute_path(cmd);

		if (cmd[0] == NULL)
			printf("Command not found\n");
		else
			exec_cmd(cmd);

		write(1, "$> ", 3);
		free_array(cmd);

	}

	printf("Bye \n");
	free(buffer);
	}
```

A ce stade, notre shell execute une coommande mais n'a pas de builtin, ni d'environemnt.

On va maintenant ajouter quelque builtin a notre shell.

## 4) Built-in

Une builtin est une commande coder dans notre shell. C'est a dire une commande qui ne va pas s'executer avec execve.

Si on lance bash et que l'on supprime la variable d'environement `PATH`, notre shell doit quand meme pouvoir executer des commandes rudimentaire.

les commandes `cd, pwd, export, echo, exit ...` doivent etre executable.

Vous pouvez lister toutes les builtin sous bash avec la commande `help`

Nous allons voir les builtin `cd, pwd` . Il en existe beacoup d'autre mais le but est juste que vous compreniez qu'est ce qu' une builtin et comment les implementer.

Pour la builtin `cd`, nous allons utiliser la fonction `chdir`

`chdir` prend en parametre le path qui va devenir le dossier courant.

Une exemple d'implementaion de la builtin `cd` :

```
void	built_in_cd(char *path)
{
	if (chdir(path) == -1) {
		perror("chdir()");
	}
}
```

Un exemple de la builtin `pwd` :

```
void	built_in_pwd(void)
{
	char cwd[PATH_MAX];
	
	if (getcwd(cwd, sizeof(cwd)) != NULL) {
	       printf("%s\n", cwd);
	} else {
		perror("getcwd()");
	}
}
```

Le code a jour avec la gestion des built-in :

```
// Les deux includes a ajouter pour le type bool et le define PATH_MAX
#include <stdbool.h>
#include <linux/limits.h>

static bool	is_built_in(char *cmd)
{
	const char	*built_in[] = {"pwd", "cd", NULL};

	for (int i = 0; built_in[i]; i++) {
		if (!strcmp(built_in[i], cmd))
			return (true);
	}
	return (false);
}

static void	exec_built_in(char **built_in)
{
	if (!strcmp(built_in[0], "pwd"))
		built_in_pwd();
	else if (!strcmp(built_in[0], "cd"))
		built_in_cd(built_in[1]);
}

int	main()
{
	char	*buffer = NULL;
	size_t	buf_size = 2048;
	char	**cmd = NULL;

	// alloc buffer qui stockera la commande entree par l'user
	buffer = (char *)calloc(sizeof(char), buf_size);
	if (buffer == NULL) {
		perror("Malloc failure");
		return (EXIT_FAILURE);
	}

	// ecriture d'un prompt
	write(1, "$> ", 3);

	// lecture de STDIN en boucle
	while (getline(&buffer, &buf_size, stdin) > 0) {
		cmd = split(buffer, " \n\t");

		if (cmd[0] == NULL)
			printf("Command not found\n");
		else if (is_built_in(cmd[0]) == false) {
			get_absolute_path(cmd);
			exec_cmd(cmd);
		} else
			exec_built_in(cmd);

		write(1, "$> ", 3);
		free_array(cmd);

	}

	printf("Bye \n");
	free(buffer);
}

```

Nous avons maintenant un shell qui peut executer une commande avec execve et des builtin :D.

Nous allons voir maintenant une chose importante dans un shell, l'environement.

## 5) l'environement

Dans n'importe quel shell unix, la commande `env` affiche les variables d'environement.

Une variable d'environement sert a communiquer des informations entre plusieurs programme.

En C, on peut recuperer l'ensemble des variables d'environement par le 3eme argument de la fonction main, char **envp.

On peut soit cree un environement en dupliquant la variable envp, et/ou coder en dur un environement minimaliste.

Nous allons coder une fonction qui stock les variables d'environement dans une liste chainee.

Si un utilisateur veut ajouter ou supprimer une variable, nous aurons juste a ajouter ou supprimer un maillon de notre liste :D.

Voila la liste des variables qui seront ajouter si elle n'existe pas dans envp :

- PATH : Pour avoir la liste des dossiers ou chercher les binaires a executer
- HOME : Pour connaitre ou est notre home :D
- OLDPWD : Pour connaitre le dossier dans lequel nous etions
- PWD : Pour connaitre le path actuelle
- SHLVL : Pour savoir combien de shell nous avons lancer

On commence par ecrire notre fonction qui va dupliquer l'env.

```
static void	dup_env(char **envp)
{
	char	*var_lst[] = {"PATH", "HOME", "OLDPWD", "SHLVL", NULL};
	ssize_t	nb_elem = 4; // nombre d'element dasn var_lst

	// boucle sur l'env et stock les variables dans la liste
	for (int i = 0; envp[i]; i++) {
		add_tail(envp[i]);

		// On verifie que l'on a les variables d'environement minimal
		if (!strncmp(envp[i], "PATH", 4)) var_lst[0] = NULL;
		else if (!strncmp(envp[i], "HOME", 4)) var_lst[1] = NULL;
		else if (!strncmp(envp[i], "OLDPWD", 6)) var_lst[2] = NULL;
		else if (!strncmp(envp[i], "SHLVL", 5)) var_lst[3] = NULL;
	}

	// On verifie qu l'on a les varaibles PATH, HOME, OLD_PWD et SHLVL
	for (int i = 0; i < 4; i++) {
		if (var_lst[i] != NULL)
			add_env_var(var_lst[i]);
	}
}
```
