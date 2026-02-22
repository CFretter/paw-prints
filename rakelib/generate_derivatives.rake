###############################################################################
# TASK: generate_derivatives
#
# create full, small, and thumb WebP images for image and pdf files in the
# 'objects/src' folder, writing derivatives to 'objects/full', 'objects/small',
# and 'objects/thumbs'
###############################################################################

require 'mini_magick'
require 'etc'

def process_derivative_image(filename, file_type, output_filename, size, density, quality)
  puts "Creating: #{output_filename}"
  begin
    if file_type == :pdf
      inputfile = "#{filename}[0]"
      magick = MiniMagick.convert
      magick.density(density)
      magick << inputfile
      magick.resize(size) if size
      magick.flatten
      magick.quality(quality)
      magick << output_filename
      magick.call
    else
      magick = MiniMagick.convert
      magick << filename
      magick.resize(size) if size
      magick.flatten
      magick.quality(quality)
      magick << output_filename
      magick.call
    end
  rescue StandardError => e
    puts "Error creating #{output_filename}: #{e.message}"
  end
end


desc 'Generate derivative image files from collection objects'
task :generate_derivatives, [:thumbs_size, :small_size, :density, :missing, :quality, :input_dir, :output_dir] do |_t, args|
  # set default arguments
  # default image size is based on max pixel width they will appear in the base template features
  args.with_defaults(
    thumbs_size: '450x',
    small_size: '800x800',
    density: '300',
    missing: 'true',
    quality: '80',
    input_dir: 'objects/src',
    output_dir: 'objects'
  )

  # set the folder locations
  input_dir  = args.input_dir
  output_dir = args.output_dir
  full_image_dir  = output_dir + '/full'
  thumb_image_dir = output_dir + '/thumbs'
  small_image_dir = output_dir + '/small'

  # Ensure that the output directories exist.
  [input_dir, full_image_dir, thumb_image_dir, small_image_dir].each do |dir|
    FileUtils.mkdir_p(dir) unless Dir.exist?(dir)
  end

  # support these file types
  EXTNAME_TYPE_MAP = {
    '.jpeg' => :image,
    '.jpg' => :image,
    '.pdf' => :pdf,
    '.png' => :image,
    '.tif' => :image,
    '.tiff' => :image
  }.freeze

  # CSV output
  list_name = File.join(output_dir, 'object_list.csv')
  field_names = 'filename,object_location,image_small,image_thumb'.split(',')

  files = Dir.glob(File.join(input_dir, '*')).reject do |f|
    File.directory?(f) || File.basename(f) == 'README.md' || File.basename(f) == 'object_list.csv'
  end

  num_threads = [Etc.nprocessors, files.size].min
  queue   = Queue.new
  files.each { |f| queue << f }

  mutex    = Mutex.new
  csv_rows = []

  threads = num_threads.times.map do
    Thread.new do
      while (filename = (queue.pop(true) rescue nil))
        extname   = File.extname(filename).downcase
        file_type = EXTNAME_TYPE_MAP[extname]
        unless file_type
          mutex.synchronize do
            puts "Skipping file with unsupported extension: #{filename}"
            csv_rows << [File.basename(filename), "/#{filename}", nil, nil]
          end
          next
        end

        base_filename  = File.basename(filename, '.*').downcase
        full_filename  = File.join(full_image_dir,  "#{base_filename}.webp")
        thumb_filename = File.join(thumb_image_dir, "#{base_filename}_th.webp")
        small_filename = File.join(small_image_dir,  "#{base_filename}_sm.webp")

        if args.missing == 'false' || !File.exist?(full_filename)
          process_derivative_image(filename, file_type, full_filename, nil, args.density, args.quality)
        else
          mutex.synchronize { puts "Skipping: #{full_filename} already exists" }
        end

        if args.missing == 'false' || !File.exist?(thumb_filename)
          process_derivative_image(filename, file_type, thumb_filename, args.thumbs_size, args.density, args.quality)
        else
          mutex.synchronize { puts "Skipping: #{thumb_filename} already exists" }
        end

        if args.missing == 'false' || !File.exist?(small_filename)
          process_derivative_image(filename, file_type, small_filename, args.small_size, args.density, args.quality)
        else
          mutex.synchronize { puts "Skipping: #{small_filename} already exists" }
        end

        mutex.synchronize do
          csv_rows << [File.basename(filename), "/#{full_filename}", "/#{small_filename}", "/#{thumb_filename}"]
        end
      end
    end
  end

  threads.each(&:join)

  CSV.open(list_name, 'w') do |csv|
    csv << field_names
    csv_rows.sort_by { |r| r[0] }.each { |r| csv << r }
  end
  puts "\e[32mSee '#{list_name}' for list of objects and derivatives created.\e[0m"
end
