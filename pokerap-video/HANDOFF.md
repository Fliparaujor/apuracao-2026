# Vídeo Pokérap com cartas: passagem de bastão

Projeto: refazer o reel "Who's that Pokémon / Pokérap" (silhueta → revelação, grade da Pokédex no refrão)
sem o tom cômico, com UMA carta real por Pokémon, lettering animado, em partes de ~1 min cobrindo os 151.

Arquivos de mídia NÃO estão no repo. Subir de novo na sessão nova:
- o reel de referência (mp4, 720x1280, 59,6 s)
- `Original_PokeRap_Gotta_Catch__Em_All_xMk8wuw7nek.mp3` (188,4 s, versão com narração "We gotta rap some Pokémon!")

## O que já existe
- `render.py`: gera o vídeo 720x1280 @30fps com PIL + ffmpeg a partir de um timeline JSON.
  Fundo de raios girando, verso da carta (pokébola) que vira no instante do nome, flash, nome em cima,
  grade 13x12 no refrão com as cartas já capturadas. Protótipo da estrofe 1 aprovado pelo usuário ("top").
  `data/tl_stanza1.json` é o formato do timeline (os caminhos `file` apontam para a sessão antiga; regenerar).
- `pick.py`: escolhe carta por nome a partir de github.com/PokemonTCG/pokemon-tcg-data (cards/en/<set>.json).
  Baixar imagens com curl (urllib toma 403). images.pokemontcg.io funciona; a API api.pokemontcg.io é instável.
- `transcribe.py`: faster-whisper small.en com timestamps por palavra (decodifica via ffmpeg; o av do pip quebra).
  Resultado em `data/palavras_whisper.json` ([inicio, fim, palavra]).
- Fonte: `fonts/LuckiestGuy.ttf` (Google Fonts, Apache).

## Pedidos do usuário ainda pendentes
1. Animar os letterings (letra por letra com pop/overshoot, palavras do refrão entrando no tempo, "POKÉMON!" ondulando).
2. Partes de ~1 min cobrindo os 151.
3. Só as cartas MAIS ICÔNICAS de cada Pokémon. Regra proposta: carta da era Wizards 1999–2000 com nome exato
   (sem "Dark X" / "Brock's X"), ranqueada por raridade (Rare Holo > Rare > Uncommon > Common > Promo) e depois
   por set (base1, base2, base3, base5, gym1, gym2, basep, base4, base6). Todos os 151 têm carta nesses sets.

## Estrutura da música (tempos do mp3)
Cada nome cai numa batida de ~0,515 s. Estrofes (primeiro nome → último):
V1 15,36–23,1 | refrão 23,8–26,5 | ponte "I'll search across the land" 26,5–35,3
V2 35,86–43,5 | refrão 44,2–48,1
V3 49,1–57,0 | refrão 57,4–63,3
V4 65,4–73,3 | ponte "At least 150..." 74,4–82,8
V5 84,1–91,9 | fala "halfway point" 92,7–100,3
V6 100,3–108,1 | refrão 108,8–112,3
V7 112,7–120,5 (slot 7 é "Pokémon!", sem nome) | ponte 121,8–129,9
V8 131,2–139,0 (um slot vazio depois de Omastar) | fala 139,4–147,4 ("Now it gets tricky")
V9 147,4–155,0 (15 nomes) | refrão 156–161,8
V10 164,3–170,7 (9 nomes, irregular, usar tempos do whisper refinados por onset) | "That's all, folks!" | refrão final até 188,4

Ordem dos nomes (150; o Mew não é cantado, entra como bônus no fim):
V1 Electrode, Diglett, Nidoran ♂, Mankey, Venusaur, Rattata, Fearow, Pidgey, Seaking, Jolteon, Dragonite, Gastly, Ponyta, Vaporeon, Poliwrath, Butterfree
V2 Venomoth, Poliwag, Nidorino, Golduck, Ivysaur, Grimer, Victreebel, Moltres, Nidoking, Farfetch'd, Abra, Jigglypuff, Kingler, Rhyhorn, Clefable, Wigglytuff
V3 Zubat, Primeape, Meowth, Onix, Geodude, Rapidash, Magneton, Snorlax, Gengar, Tangela, Goldeen, Spearow, Weezing, Seel, Gyarados, Slowbro
V4 Kabuto, Persian, Paras, Horsea, Raticate, Magnemite, Kadabra, Weepinbell, Ditto, Cloyster, Caterpie, Sandshrew, Bulbasaur, Charmander, Golem, Pikachu
V5 Alakazam, Doduo, Venonat, Machoke, Kangaskhan, Hypno, Electabuzz, Flareon, Blastoise, Poliwhirl, Oddish, Drowzee, Raichu, Nidoqueen, Bellsprout, Starmie
V6 Metapod, Marowak, Kakuna, Clefairy, Dodrio, Seadra, Vileplume, Krabby, Lickitung, Tauros, Weedle, Nidoran ♀, Machop, Shellder, Porygon, Hitmonchan
V7 Articuno, Jynx, Nidorina, Beedrill, Haunter, Squirtle, Chansey, Parasect, Exeggcute, Muk, Dewgong, Pidgeotto, Lapras, Vulpix, Rhydon
V8 Charizard, Machamp, Pinsir, Koffing, Dugtrio, Golbat, Staryu, Magikarp, Ninetales, Ekans, Omastar, Scyther, Tentacool, Dragonair, Magmar
V9 Sandslash, Hitmonlee, Psyduck, Arcanine, Eevee, Exeggutor, Kabutops, Zapdos, Dratini, Growlithe, Mr. Mime, Cubone, Graveler, Voltorb, Gloom
V10 Charmeleon, Wartortle, Mewtwo, Tentacruel, Aerodactyl, Omanyte, Slowpoke, Pidgeot, Arbok

Cálculo dos tempos: por estrofe, ajustar reta t = t0 + i*p pelos tempos do whisper (que erra ~0,1–0,2 s e
transcreve nomes errado, ex. "Polyrath", "Firebloom"), e refinar cada nome no pico de onset (fluxo espectral) a ±60 ms.
A revelação acontece no onset do nome; o verso da carta aparece ~0,26 s antes.

## Divisão proposta (cortes em fim de refrão/ponte, com fade curto)
Parte 1: 0,0–64,0 s (V1–V3, 48 Pokémon)
Parte 2: 64,0–130,4 s (V4–V7, 63 Pokémon)
Parte 3: 130,4–188,4 s (V8–V10 + Mew bônus no final, 40 Pokémon)
A grade/contador "N/151" é acumulativa entre as partes.
Trechos sem nomes (intro, pontes, falas): grade + contador + lettering da letra cantada; falas como legenda menor.
Correções do whisper na intro: "wrap" → "rap", "rats" → "rest".
