###############################################################################
# TASK: generate_banner
#
# Generate a cropped banner image for the home page from the objectid set as
# featured-image in _data/theme.yml. Output goes to assets/img/banner.webp
# and theme.yml's banner-image is updated to point to it.
#
# Usage:
#   bundle exec rake generate_banner
#   bundle exec rake generate_banner[paw_123]          # override objectid
#   bundle exec rake generate_banner[paw_123,1600,600] # custom dimensions
###############################################################################

require 'mini_magick'
require 'yaml'

desc 'Generate a cropped banner image for the home page'
task :generate_banner, [:objectid, :width, :height, :quality] do |_t, args|
  theme = YAML.load_file('_data/theme.yml')

  args.with_defaults(
    objectid: theme['featured-image'] || 'paw_052',
    width:    '1400',
    height:   '500',
    quality:  '85'
  )

  src = Dir.glob("objects/src/#{args.objectid}.*").first
  abort "Source image not found for objectid '#{args.objectid}' in objects/src/" unless src

  FileUtils.mkdir_p('assets/img')
  out  = 'assets/img/banner.webp'
  size = "#{args.width}x#{args.height}"
  puts "Creating banner #{size} from #{src} → #{out}"

  magick = MiniMagick.convert
  magick << src
  magick.resize("#{args.width}x")
  magick.gravity('Center')
  magick.geometry('+0-250')  # skip 150px from top before cropping
  magick.extent(size)
  magick.quality(args.quality)
  magick << out
  magick.call

  puts "\e[32mDone: #{out}\e[0m"
end
