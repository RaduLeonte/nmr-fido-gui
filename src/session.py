from src.spectrum import Spectrum


class Session:
    
    def __init__(self):
        self.spectra: list[Spectrum] = []
        self.active_spectrum_index = None
        self.active_spectrum = None
    
    
    def import_spectra(self, paths: list[str]) -> list[Spectrum]:
        for path in paths:
            print(f"Session.import_spectra -> Loading:{path}")
            self.spectra.append(
                Spectrum(path)
            )
            
        if self.active_spectrum is None:
            self.active_spectrum_index = 0
            self.active_spectrum = self.spectra[0]
    
    
    def get_active_spectrum_index(self) -> int:
        return self.active_spectrum_index
    
    
    def set_active_spectrum_index(self, index: int=0) -> None:
        self.active_spectrum_index = index
    
    
    def get_active_spectrum(self) -> Spectrum:
        return self.active_spectrum
    
    
    def get_spectrum(self, index: int) -> Spectrum:
        return self.spectra[index]
    
    
    def get_spectra_count(self) -> int:
        return len(self.spectra)
    
    
    def get_spectra_base_paths(self) -> list[str]:
        return [s.base_path for s in self.spectra]
    
    
    def save(self) -> None:
        return
    
    
    def load(self) -> None:
        return