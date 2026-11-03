{
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/f13ff45afd1bb73e640eaa08a7066dbed07e3238";
  outputs = { self, nixpkgs }: let
    system = "x86_64-linux";
    pkgs = import nixpkgs { inherit system; config.allowUnfree = true; };
  in {
    devShells.${system} = {
      default = pkgs.mkShell {
        packages = [ pkgs.open-watcom-v2 pkgs.python3 pkgs.dosbox-x ];
      };
      ci = pkgs.mkShell {
        packages = [ pkgs.python3 pkgs.dosbox-x ];
      };
    };
  };
}
