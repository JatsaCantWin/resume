{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };
        tex = pkgs.texliveSmall.withPackages (ps: [
          ps.enumitem
          ps.titlesec
          ps.lastpage
          ps.soul
          ps.xhfill
          ps.fontawesome5
          ps.totalcount
          ps.biblatex
          ps.fira
          ps.raleway
          ps.sourcesanspro
          ps.montserrat
          ps.inter
          ps.libertinus
          ps.libertinus-type1
          ps.scholax
          ps.charter
          ps."tex-gyre"
          ps."cm-super"
          ps.fontaxes
          ps.xstring
          ps.ly1
          ps.psnfss
        ]);
      in
      {
        devShells.default = pkgs.mkShell {
          packages = [
            tex
            pkgs.biber
          ];
        };
      }
    );
}
