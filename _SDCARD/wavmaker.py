import os
import sys
import wave
import audioop


def base_dir():
    """Folder to process.

    When packaged as a Windows .exe (PyInstaller), __file__ points at a private
    temp extraction dir, so use the folder where the .exe actually lives.
    When run as a normal Python script, use the script's own folder.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def is_frozen():
    return getattr(sys, "frozen", False)


def process_wav_file(file_path, new_path):
    with wave.open(file_path, 'rb') as wav_file:
        params = wav_file.getparams()
        frames = wav_file.readframes(params.nframes)

        # Convert to Mono if needed
        if params.nchannels > 1:
            frames = audioop.tomono(frames, params.sampwidth, 1, 0)

        # Change sample width to 16-bit if needed
        if params.sampwidth != 2:
            frames = audioop.lin2lin(frames, params.sampwidth, 2)

        # Change sample rate to 44100 Hz if needed
        if params.framerate != 44100:
            frames, _ = audioop.ratecv(frames, 2, 1, params.framerate, 44100, None)

        # Write the processed data to a new file with the correct parameters
        with wave.open(new_path, 'wb') as new_wav_file:
            new_wav_file.setnchannels(1)
            new_wav_file.setsampwidth(2)
            new_wav_file.setframerate(44100)
            new_wav_file.writeframes(frames)


def format_wav_files(directory, start_number):
    count = start_number
    converted = 0
    for filename in sorted(os.listdir(directory)):
        # skip files that are already named _<n>.wav (avoid re-processing output)
        if not filename.lower().endswith(".wav"):
            continue
        if filename.startswith("_") and filename[1:-4].isdigit():
            continue

        file_path = os.path.join(directory, filename)
        new_filename = f"_{count}.wav"
        new_file_path = os.path.join(directory, new_filename)

        try:
            process_wav_file(file_path, new_file_path)
            os.remove(file_path)  # Delete the original file after processing
            print(f"  {filename}  ->  {new_filename}")
            count += 1
            converted += 1
        except Exception as e:
            print(f"  ! skipped {filename}: {e}")

    return converted


def main():
    directory = base_dir()
    print("ichosynth - wavmaker")
    print("Converte i WAV in questa cartella in mono / 16-bit / 44100 Hz")
    print("e li rinomina _<numero>.wav (gli originali vengono SOSTITUITI).")
    print(f"Cartella: {directory}\n")

    try:
        raw = input("Numero di partenza (es. 1 per samples/0, 100 per samples/1): ").strip()
        start_number = int(raw)
    except (ValueError, EOFError):
        print("Numero non valido. Uscita.")
        if is_frozen():
            input("\nPremi Invio per chiudere...")
        return

    n = format_wav_files(directory, start_number)
    print(f"\nFatto: {n} file convertiti.")
    if is_frozen():
        input("\nPremi Invio per chiudere...")


if __name__ == "__main__":
    main()
